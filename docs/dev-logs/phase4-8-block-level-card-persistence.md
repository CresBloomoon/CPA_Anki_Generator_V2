# Phase4-8: ブロック単位のカード保持とPARTIALLY_DONEステータス導入

## 背景

実機での生成ジョブ実行中（Gemini 2.5 Proで課金済みAPI呼び出しを含む）に、
セクション途中のブロック失敗によって、それ以前のブロックで既に生成
済み・課金済みだったカードが失われる事象が発見された。この事象を個別の
バグ修正としてではなく、「ユーザーが実際にAPI料金を払って生成したカードが
何らかの理由で失われる」シナリオの一つ（B-1）として抽象化して調査し、
まーくんと相談の上で対策方針を確定した。調査で洗い出した他のシナリオ
（インフラ再起動、フロントエンドの状態消失、重複課金リスク等）は別
トラックとして今回のスコープ外とし、本Phaseでは調査結果のうちB-1
（本Phase）とC-2（Phase5-22）のみに対応する。

## 何を実装したか

- `backend/app/domain/generation_job.py`（修正）
  - `SectionJobStatus`に`PARTIALLY_DONE`を追加。「一部のブロックは
    成功したが、途中のブロックで失敗し完走できなかった」状態を表す。
  - `mark_failed()`を、呼び出し時点で`section_job.cards`が空でなければ
    `PARTIALLY_DONE`、空であれば従来通り`FAILED`に遷移するよう変更した。
    シグネチャ自体は変更していない。
  - `collect_generated_cards()`の集計対象に`PARTIALLY_DONE`を追加し、
    部分的に生成されたカードもダウンロード対象に含まれるようにした。
- `backend/app/usecases/generate_cards_for_section_usecase.py`（修正）
  - `execute()`に`on_block_generated: Callable[[list[Card]], None] |
    None = None`引数を追加。各ブロックの生成が成功するたびに、
    **そのブロック分のカードのみ**（累積リストではない）を渡して呼び出す。
    デフォルト`None`のため、既存の呼び出し元・既存テストは無改修で動作する。
- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `run()`内で`on_block_generated=section_job.cards.extend`を渡すよう
    配線。これにより、ブロックが成功するたびに`SectionJob`（ジョブ全体を
    保持する`GenerationJob`の一部）へ即座にカードが反映されるようになった。
    途中のブロックで例外が送出されても、それ以前に`extend`済みのカードは
    `section_job.cards`に残ったままになる。
- テスト
  - `tests/domain/test_generation_job.py`（修正）：`mark_failed()`が
    カード保持済みの状態から呼ばれると`PARTIALLY_DONE`になることを
    確認するテスト、`is_complete()`が`PARTIALLY_DONE`のときも`False`に
    なることを確認するテスト、`collect_generated_cards()`が
    `PARTIALLY_DONE`のセクションのカードも含めることを確認するテストを
    追加。
  - `tests/usecases/test_generate_cards_for_section_usecase.py`（修正）：
    コールバックがブロックごとに1回、そのブロック分のカードのみで
    呼ばれることを確認するテスト、後続ブロックが失敗しても先行ブロック分は
    既にコールバックへ渡され終えていることを確認するテスト、コールバック
    省略時も従来通り動作することを確認するテストを追加。
  - `tests/usecases/test_start_generation_job_usecase.py`（修正）：
    `_FakeGenerateCardsForSectionUsecase`のシグネチャに
    `on_block_generated`を追加し、既存の`behavior`関数を新シグネチャに
    合わせて更新。実際に`on_block_generated`経由で`section_job.cards`へ
    反映され、後続ブロック失敗時に`PARTIALLY_DONE`へ遷移し
    `collect_generated_cards()`で回収できることを確認する統合テストを
    追加（今回の事象そのものを再現するテスト）。
  - `tests/usecases/test_build_anki_package_usecase.py`（修正）：
    `PARTIALLY_DONE`のセクションのカードが`.apkg`のビルド対象に含まれる
    ことを確認するテストを追加。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **コールバック方式を採用し、ジェネレータ方式は採用しなかった**：
  `GenerateCardsForSectionUsecase.execute()`の既存の戻り値契約
  （`-> list[Card]`、同期的に全カードをまとめて返す）を変更せずに済む
  ため。既存の`test_generate_cards_for_section_usecase.py`は全て
  `cards = usecase.execute(...)`という同期的な受け取り方をしており、
  ジェネレータ化するとこれら全てを`list(usecase.execute(...))`のような
  形に書き換える必要が生じる。コールバック方式であれば
  `on_block_generated=None`がデフォルトのため、既存の呼び出し元・
  既存テストへの影響がゼロで済む。
- **コールバックには「そのブロック分のカードのみ」を渡す設計にした**：
  累積リスト（それまでの全ブロックの合計）を渡す案も検討したが、
  その場合呼び出し元は「前回渡された分との差分」を自分で計算する必要が
  生じ、二重追加のリスクが生まれる。ブロック単位の差分だけを渡せば、
  呼び出し元は単純に`extend`するだけで済む。
- **`JobStore`に新しいロックを追加しなかった**：`section_job.cards.extend(...)`
  は生成用バックグラウンドスレッドから呼ばれるが、これは既存の
  `job.mark_running(index)`等と同じく、`JobStore`のロックの外側で
  `GenerationJob`インスタンスのフィールドを直接書き換える既存パターンに
  乗るだけである。この設計は「書き込みは生成用バックグラウンドスレッド
  のみ、読み込みはリクエストスレッドのみ」という単一ライター構成を前提に
  既に成立しており、リストへの`extend`もCPythonのGILの下で読み込み側が
  壊れた中間状態を観測することはないため、新たなロックを追加する必要は
  ないと判断した。
- **B-1の3つの選択肢（B-1a／B-1b／B-1c）のうち、新ステータス
  `PARTIALLY_DONE`を導入するB-1cをまーくんの判断で採用した**：
  `FAILED`のまま部分結果だけダウンロード対象に含める案（B-1b）は
  実装コストが最小だが、「バッジは"失敗"なのに枚数はN件」という
  一見矛盾した表示になりフロントエンド側の説明が必要になる。新ステータス
  を導入する方が、状態を最も正直に表現できると判断した。フロントエンド
  への波及（`STATUS_LABELS`／`STATUS_BADGE_CLASSES`／`isGenerating()`
  の判定への追加）はPhase5-21で対応する。

## 副次的な効果

`SectionJobStatusResponse.card_count`は`len(section_job.cards)`を
そのまま返す実装のため、今回の変更により**生成中でも完了したブロック分の
枚数が徐々に増えていく表示**になる（従来はセクション完了までずっと0の
ままだった）。狙った効果ではないが、副産物として記録しておく。

## ADR

今回はADRを書くレベルの設計判断はなし。
