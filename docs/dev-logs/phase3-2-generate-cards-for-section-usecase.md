# Phase3-2: セクション単位カード生成Usecase（サブシュレッディング含む）

## 実装したもの

- `backend/app/usecases/generate_cards_for_section_usecase.py`
  - `GenerateCardsForSectionUsecase.execute(section: Section, pdf_bytes: bytes) ->
    list[Card]`：1つの`Section`に対応するテキストを抽出し、必要に応じてブロック分割
    （サブシュレッディング）した上でAIリポジトリに渡し、返ってきた`CardContent`を
    `Card`（`section_title`／`deck_path`を付与）に変換する。
  - サブシュレッディングの判定は**ページ数のみ**（`5ページ超なら4ページ単位に分割`）。
    旧実装の`min_goal > 20`という条件・各ブロックへの目標枚数配分ロジックはADR 0001
    （`min_card_count`撤去）に伴い完全に削除した。
  - `Section.page_range.end_page`が`None`（文書末尾まで続く節）の場合でも、まず
    `extract_text_from_range`を1回呼んで実際に含まれる`--- ページ N ---`マーカーの数を
    数え、そこからブロック分割数を決定する（旧実装の「開始ページ+5と仮定する」という
    力技は採用していない）。
  - `SupportsExtractText`：PyMuPDF非依存の構造的Protocol（Phase3-1の`SupportsScan`と
    同じ狙い）。AI側は`AiCardGeneratorRepository`（Phase2-2の抽象クラス、
    google-genai非依存）にそのまま依存できるため、新規Protocolは不要だった。
  - AI呼び出しの失敗は握りつぶさず、そのまま呼び出し元に伝播させる（バッチ全体を
    中断するかどうかの判断はPhase3-3の責務）。
- `backend/app/repositories/ai/dto.py`／`prompt_builder.py`（Phase2-2で実装済みの
  ファイルへの変更）：`PromptContext`に`block_index`／`block_count`を追加し、
  `PromptBuilder`が生成するプロンプトに「このテキストはどの節の（分割している場合は
  何分割中の何番目の）抜粋か」という1行を追加した。Phase2-2の時点で
  `PromptContext.section_title`が実際のプロンプトに一切反映されていなかった
  （dev-log参照）という課題への対応をこのPhaseで行った。`anki_generation.md`自体は
  変更していない。
- テスト：`test_dto.py`（8ケース）、`test_prompt_builder.py`に2ケース追加、
  `test_generate_cards_for_section_usecase.py`（7メソッド、うち1つはページ数
  1／5をパラメータ化）。

## 設計判断

- サブシュレッディングの判定・ブロックへの分割は、`extract_text_from_range`の出力
  （すでに`--- ページ N ---`マーカーが埋め込まれている）を正規表現で再分割する形で
  実装した。ページ範囲を先に計算してブロックごとに`extract_text_from_range`を複数回
  呼ぶ（旧実装の方式）のではなく、1回の抽出結果を後から分割する方式にしたことで、
  「`end_page`が不明な節の合計ページ数をどう見積もるか」という問題が自然に解消される
  （実際に抽出された内容からページ数が確定するため）。
- `PromptContext.section_title`を活かす対応は、`anki_generation.md`（プロンプトの
  出力フォーマット契約ファイル）自体を変更せず、`PromptBuilder`が組み立てる周辺の
  文字列にのみ追加する形にした。テンプレート内容自体は旧リポジトリからの移植物として
  維持する方針を優先した。

## 実装中に発見したバグ・問題点

特になし（今回のバグ的な発見はテスト側の運用フロー、後述のCLAUDE.md更新を参照）。

## 動作確認

- このUsecase・`dto.py`／`prompt_builder.py`への変更はいずれもPyMuPDF・genanki・
  google-genaiのいずれにも依存しないため、サンドボックス内で直接実行し、
  テストファイルと同一のロジックで全ケースを事前に確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`124 passed`を確認済み
  （Phase3-1完了時点の107件＋今回の17件）。

なお動作確認の過程で、`docker compose build backend`を挟まずに`docker compose run
--rm backend`だけでpytestを実行すると、新規追加したテストファイルがイメージ内の
古いソースのままテスト収集されず「107 passed」のまま変化しないという事象が発生した。
これはコードのバグではなく運用上の見落としだったため、CLAUDE.mdに「Docker確認は
変更の大小に関わらず毎回`docker compose build backend`から行う」という運用ルールを
追記した（別コミット）。

## ADR

`PromptContext`への`block_index`/`block_count`追加、サブシュレッディング判定の
ページ数のみへの単純化はいずれもADR 0001の帰結として論理的に導かれる判断であり、
新たなADRを起票するほどの分岐ではないと判断した。
