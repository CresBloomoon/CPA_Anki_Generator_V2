# Phase7-2-4: 履歴一覧取得API

## 背景

Phase7-2-1〜7-2-3で、`GenerationJob`のディスク永続化と、`job_id`を指定した
1件取得（再起動後のフォールバック含む）までが実装済みだった。本Phaseは
「過去にどんなジョブが存在するか」を一覧で取得するAPIを新設する。

現状把握の結果、以下を確認した上で実装した。
- `GenerationJob`に一覧の並び替え・表示に使えるジョブ単位のタイムスタンプ
  が無かった（`SectionJob.started_at`/`finished_at`はセクション単位）
- `GenerationJobRepository`に全件列挙する機能が無かった（Phase7-2-1の
  dev-logに記載した通り、消費箇所ができるまで意図的に見送っていた）
- `JobStore`のメモリ上の辞書は、再起動後は個別に`get(job_id)`された分だけ
  遅延ロードされる不完全な部分集合であり、一覧の情報源としては使えない
  （リポジトリ設定時はリポジトリ側を情報源にする必要がある）

## 何を実装したか

- `backend/app/domain/generation_job.py`（修正）
  - `GenerationJob`に`created_at: datetime`フィールドを追加。
    `field(default_factory=lambda: datetime.now(timezone.utc))`をデフォルト
    にし、直接構築している既存テストへの後方互換を保った
- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `execute()`で`GenerationJob`生成時に`created_at=datetime.now(timezone.
    utc)`を明示的に渡すようにした（`idempotency_key`/`root_path`と同様、
    ドメイン側のデフォルト値に暗黙的に頼らない）
- `backend/app/repositories/jobs/generation_job_serializer.py`（修正）
  - `job_to_dict`/`job_from_dict`に`created_at`の`.isoformat()`／
    `datetime.fromisoformat()`変換を追加
- `backend/app/repositories/jobs/generation_job_repository.py`（修正）
  - `list_all() -> list[GenerationJob]`を新設。ディレクトリが存在しなければ
    空リストを返す。並び替えは行わない（`find_by_idempotency_key`と同じく
    「素朴な取得のみ」に徹し、順序の決定は呼び出し元に委ねる）
- `backend/app/repositories/jobs/job_store.py`（修正）
  - `list_all() -> list[GenerationJob]`を新設。リポジトリが設定されていれば
    リポジトリ（ディスク）を情報源にし、未設定ならメモリ上の辞書を情報源に
    する
- `backend/app/usecases/list_generation_jobs_usecase.py`（新規）
  - `ListGenerationJobsUsecase`：`job_store.list_all()`の結果を`created_at`
    の新しい順にソートして返す。既存の`GetGenerationJobStatusUsecase`
    （1件取得専任）とは責務を分け、新規usecaseとして独立させた
- `backend/app/routes/schemas/generation.py`（修正）
  - `GenerationJobSummaryResponse`（`job_id`/`root_path`/`created_at`/
    `is_complete`/`section_count`/`done_section_count`）・
    `GenerationJobListResponse`を新設。既存の`GenerationJobStatusResponse`
    （セクションごとの詳細を持つ）とは別の、一覧表示専用の軽量スキーマ
  - `done_section_count`は`DONE`＋`PARTIALLY_DONE`の合計とした（まーくんの
    決定：「今何がダウンロードできるか」という観点でフロントの既存
    `doneCount`ロジックと統一するため。`is_complete`が`DONE`のみを完了と
    みなすのとは異なる集計軸になるが、それぞれ別目的の値として問題ない）
- `backend/app/routes/generation_routes.py`（修正）
  - `GET /generation-jobs`を新設。既存の`POST /generation-jobs`とはHTTP
    メソッドが異なり、`GET /generation-jobs/{job_id}`とはパスの形（セグ
    メント数）が異なるため、ルーティング上の衝突は無い
- テスト
  - `test_generation_job_repository.py`：`TestListAll`クラスを新設
    （ディレクトリ未作成時・空ディレクトリ時は空リスト、複数保存後は全件
    返ることを確認）。既存の往復テストに明示的な`created_at`を追加
  - `test_job_store.py`：`TestListAll`クラスを新設（リポジトリ未設定時は
    メモリのみ、設定時は`job_store`を経由せず`repository.save()`で直接
    書き込んだジョブも一覧に含まれることを確認）
  - `test_list_generation_jobs_usecase.py`（新規）：0件時は空リスト、複数
    ジョブが`created_at`の新しい順にソートされることを確認
  - `test_start_generation_job_usecase.py`：`execute()`が`created_at`を
    「おおよそ今」に設定することを確認するテストを追加
  - `test_generation_routes.py`：`TestListGenerationJobs`クラスを新設
    （未実行時は空リスト、完了後は`job_id`/`root_path`/`created_at`/
    `is_complete`/`section_count`/`done_section_count`が正しく返ること、
    複数ジョブが新しい順で返ることを確認）。`_start_generation_job()`
    ヘルパーに`root_path`引数を追加

## 実装中に発見したバグ・問題点

実装完了後のpytest実行で、Phase7-2-3で追加済みだった
`test_get_falls_back_to_the_repository_when_missing_from_memory`が
1件失敗した。

```
assert GenerationJob(...) == GenerationJob(...)
Differing attributes: ['created_at']
```

調査の結果、このテストは`_make_job("job-1")`を独立に2回呼び出し
（1回目は`repository.save(...)`用、2回目はアサーション内の比較用）、
`==`で比較していた。`test_job_store.py`内の`_make_job()`ヘルパーは
`created_at`を明示的に渡しておらず、`GenerationJob`側の
`default_factory=lambda: datetime.now(timezone.utc)`に委ねていたため、
2回の呼び出しでそれぞれ別の（数百マイクロ秒ズレた）`created_at`が入り、
他のフィールドが全て一致していても等価比較全体が失敗していた。

これは`created_at`追加によって初めて顕在化した問題で、Phase7-2-1〜7-2-3
時点では`_make_job()`にタイムスタンプを持つフィールドが無かったため
発生し得なかった。実装（`GenerationJob`・`JobStore`・
`GenerationJobRepository`）側には問題が無いことを確認した上で、
`test_job_store.py`の`_make_job()`に`created_at: datetime = datetime(2026,
1, 1, tzinfo=timezone.utc)`という固定デフォルト値付き引数を追加し、
`GenerationJob`構築時にそのまま渡すよう修正した。引数を省略した既存の
呼び出し元は全て無改修のまま動作し、他の3ファイル（`test_generation_job.
py`・`test_list_generation_jobs_usecase.py`・
`test_get_generation_job_status_usecase.py`）にある同名だがファイル内
限定の別の`_make_job()`ヘルパーには一切影響しないことを確認した。

## 大きな判断とその理由

- **`created_at`のデフォルト値をドメイン側の`field(default_factory=...)`
  に任せず、`StartGenerationJobUsecase.execute()`側でも明示的に設定した**：
  `idempotency_key`・`root_path`が既に「ドメイン側はテスト用の無害な
  デフォルト、実際の値の決定と設定はusecase層の責務」という構成になって
  おり、それと一貫させるため
- **`GenerationJobRepository.list_all()`・`JobStore.list_all()`のどちらも
  並び替えを行わない設計にした**：`find_by_idempotency_key()`が「素朴な
  lookupのみに徹し、それが今も duplicateとして扱われるかどうかの判断は
  呼び出し元に委ねる」という既存の設計方針（Phase4-9）を踏襲し、「新しい
  順に並べる」というポリシー判断は`ListGenerationJobsUsecase`に閉じ込めた
- **`JobStore.list_all()`は、リポジトリ設定時はメモリではなくリポジトリを
  情報源にする**：`JobStore.get()`のディスクフォールバック（Phase7-2-3）
  は個別の`job_id`が問い合わせられた時だけ遅延的にメモリへ載せる設計の
  ため、再起動直後はメモリ上の辞書が「ディスク上の全ジョブの不完全な
  部分集合」でしかない。一覧としての完全性を保証するには、リポジトリが
  設定されている限りリポジトリを直接読む必要があると判断した
- **`GenerationJobStatusResponse`を流用せず、一覧専用の軽量スキーマ
  （`GenerationJobSummaryResponse`）を新設した**：まーくんとの事前合意
  通り、一覧表示に不要なセクションごとの詳細（`status`/`card_count`/
  `error_message`/`elapsed_seconds`）を持たせないようにするため
- **`done_section_count`の集計対象を`DONE`＋`PARTIALLY_DONE`にした**：
  まーくんの決定に基づく。履歴一覧の目的が「過去のジョブから今何が
  ダウンロードできるか」であるため、フロントの既存`doneCount`ロジック
  （ダウンロード可否の観点）と統一した。`is_complete`（`DONE`のみを完了
  とみなす）とは異なる集計軸になるが、それぞれ別目的の値として問題ない

## ADR

今回はADRを書くレベルの設計判断はなし。
