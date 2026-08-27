# Phase3-5: 連続失敗閾値によるバッチ中断への見直し（B-2）

## 背景

APIコスト損失調査で洗い出したB-2（1セクションが失敗すると、それ以降の全
セクションが一切試行されずPENDINGのまま永久に止まる仕様）への対応。まーくんと
相談の上、「1回の失敗では止めず、連続して一定回数（既定2回）失敗した場合のみ
バッチを中断する」という仕様に変更した。

現状把握の結果、旧仕様は`StartGenerationJobUsecase.run()`の`except`節にある
`break`のみで実現されており、この`break`はコード中のコメント
（`# any failure aborts the batch`）と既存テストのdocstring
（`test_one_failure_stops_the_batch_but_keeps_completed_sections`、
「Phase3-3 acceptance scenario」）の両方から、意図的な設計判断であることを
確認した上で着手した。

## 何を実装したか

- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `__init__`に`max_consecutive_failures: int = 2`を追加。既存の
    `job_store`/`pdf_store`/`generate_cards_for_section_usecase`と同じ
    DIスタイル（コンストラクタ引数）に合わせた。
  - `run()`のループに`consecutive_failures`というローカル変数を導入。
    `job.mark_done()`の直後に0へリセットし、`job.mark_failed()`の直後に
    +1して、`max_consecutive_failures`に達した場合のみ`break`する形に
    変更。1回の失敗だけでは次のセクションへ処理が続くようになった。
- `backend/tests/usecases/test_start_generation_job_usecase.py`（修正）
  - 既存の受け入れシナリオテスト
    （`test_one_failure_stops_the_batch_but_keeps_completed_sections`）を、
    4セクション構成で2番目・3番目が連続失敗し4番目が未着手のままPENDINGに
    なることを確認する
    `test_consecutive_failures_reaching_the_threshold_stops_the_batch_but_keeps_completed_sections`
    に作り替えた。`max_consecutive_failures`はデフォルト値（2）のまま構築し、
    実際に本番で使われる閾値そのものの挙動を検証する形にした。
  - 新規テストを3件追加：
    - `test_a_single_failure_does_not_stop_the_batch`：1回の失敗だけでは
      次のセクションが実際に試行されることを確認
    - `test_success_resets_the_consecutive_failure_count`：成功を挟むと
      連続失敗カウントがリセットされることを確認（1成功→2失敗→3成功→
      4失敗→5失敗で5番目まで到達したところで停止し、6番目は未着手のまま
      になるシナリオ）
    - `test_cards_from_a_section_after_a_skipped_failure_are_collected`：
      スキップして継続した先の成功セクションのカードが
      `collect_generated_cards()`にきちんと含まれることを確認

## 実装中に発見したバグ・問題点

なし。フロントエンド（`GenerationProgress.tsx`／`DownloadButton.tsx`／
`App.tsx`）は、いずれも各`section_jobs`をステータス種別のみでフィルタ・
カウントしており、「FAILEDは1件のみ・必ず最後に来る」という位置的な前提を
置いたコードは無いことを実装時に再確認した。今回の仕様変更（FAILEDの後に
DONEが来る順序が新たに発生し得る）による追加の変更は不要だった。

## 大きな判断とその理由

- **連続失敗カウンタは`GenerationJob`（ドメイン層）ではなく、
  `StartGenerationJobUsecase.run()`のローカル変数として実装した**：
  「1セクション失敗時に残りをどう扱うか」という判断は、旧仕様の時点で
  既に`GenerationJob`エンティティには一切現れず、usecase層の`break`にのみ
  存在していた。連続失敗カウントも同様に、「今どのセクションがどんな状態か」
  というドメインの事実ではなく、`run()`という1回のバッチ実行の過程で
  一時的に必要になるだけの情報であり、`run()`終了後は各`SectionJob`の
  `status`を見れば結果を再現できるため、ドメイン層に持たせる必要はないと
  判断した。
- **閾値はモジュール定数ではなくコンストラクタ引数にした**：フロントエンドの
  `GenerationProgress.tsx`には同種の概念（`MAX_CONSECUTIVE_POLL_FAILURES`、
  ポーリング失敗の連続回数閾値）がモジュール定数として存在するが、バックエンド
  側では`StartGenerationJobUsecase`が既に全ての依存をコンストラクタ引数で
  受け取るDIスタイルを採っているため、それに合わせてコンストラクタ引数とした。
  テストから閾値を変えて「1回失敗しただけで止まるケース」等を検証しやすい
  という利点もある。
- **既存の受け入れシナリオテストを、デフォルト値（2）のまま4セクション構成に
  作り替えた**：閾値を1にオーバーライドして既存の3セクション構成をほぼ
  そのまま流用する案も検討したが、この特定のテストは元々「Phase3-3の受け入れ
  シナリオ」として、このusecase全体の代表的な振る舞いを検証する位置づけを
  持っていた。閾値をテスト専用の値にオーバーライドすると、将来デフォルト値を
  調整した際にこの代表テストがその変更を検知できなくなるため、実際の本番
  デフォルト値そのものを検証できる4セクション構成を優先した。
- **`SectionJobStatus`への新ステータス追加は行わなかった**：`PENDING`は
  「まだ試行されていない」という意味のまま変わらず、連続失敗による停止と
  それ以外の停止理由を区別する必要はない。直前の（最大`max_consecutive_
  failures`件の）`SectionJob`の`status`／`error_message`を見れば、なぜ
  止まったかは十分追える。

## ADR

今回はADRを書くレベルの設計判断はなし。
