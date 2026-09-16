# Phase7-2-1: 履歴機能のためのジョブ永続化基盤

## 背景

Step7-2（履歴機能）の実装に向けた最初のPhase。現状把握の結果、`JobStore`
（`backend/app/repositories/jobs/job_store.py`）は完全インメモリで、
バックエンド再起動でジョブが失われる実装だった。履歴機能はジョブごとに
1ファイルのJSONとして永続化し、ブロック完了ごとに書き込む設計で合意した。
本Phaseはそのうち「ドメイン+永続化基盤」の部分（バックエンドのみ）を扱う。
ブロック単位の書き込みトリガー・再起動後の読み込み対応・履歴一覧API・
フロントエンドUI・root_pathのフロント配線は、いずれも後続のPhase
（7-2-2〜7-2-6）で扱う。

## 何を実装したか

- `backend/app/repositories/jobs/generation_job_serializer.py`（新規）
  - `GenerationJob`/`SectionJob`/`Section`/`PageRange`/`DeckPath`/`Card`/
    `CardContentItem`のオブジェクトグラフをJSON安全な`dict`に相互変換する
    `job_to_dict()`/`job_from_dict()`（および各内部ヘルパー）を実装
  - `dataclasses.asdict()`任せにはできない3点（`SectionJobStatus`は
    Enum→`.name`変換、`started_at`/`finished_at`は`datetime`→
    `.isoformat()`変換、`DeckPath.segments`はtuple→list変換）を全フィールド
    明示的にマッピングして解決した
  - ドメイン層自体にシリアライズ責務を持たせず、リポジトリ層のこのモジュール
    だけがJSON形式を知っている、という責務分離にした
- `backend/app/repositories/jobs/generation_job_repository.py`（新規）
  - `RootPathHistoryRepository`と同じ「1ファイルJSON読み書き」パターンで
    `save(job)`・`get(job_id) -> GenerationJob | None`を実装
  - 保存先は`backend/data/generation_jobs/{job_id}.json`（ジョブごとに1
    ファイル）。既存の`.gitignore`の`backend/data/`エントリ、docker-compose
    のバインドマウントがそのまま使えるため追加設定は不要だった
  - `list()`相当は今回作らず、実際の消費箇所ができるPhase7-2-4まで見送った
- `backend/app/repositories/jobs/job_store.py`（修正）
  - コンストラクタで`GenerationJobRepository | None`を受け取れるようにし、
    `None`の場合は従来通り完全インメモリのまま（既存の全テストが無改修で
    通ることを確認済み）
  - `save()`の中で、リポジトリが設定されていれば書き込みも行う
- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `execute()`に`root_path: str = ""`引数を追加し、`GenerationJob`生成時に
    渡すようにした
  - `run()`内で`mark_running`/`mark_done`/`mark_failed`の直後にそれぞれ
    `self._job_store.save(job)`を追加。ジョブオブジェクトは生成時に一度
    `job_store`へ登録された後、直接ミューテーションで状態が変わる設計
    だったため、永続化を発火させるには明示的な再saveが必要だった
    （「セクション単位」の書き込みトリガー。「ブロック単位」への拡張は
    Phase7-2-2で行う）
- `backend/app/domain/generation_job.py`（修正）
  - `GenerationJob`に`root_path: str = ""`フィールドを追加
- `backend/app/routes/schemas/generation.py`（修正）
  - `StartGenerationRequest`に`root_path: str = ""`フィールドを追加
    （フロントエンドからの送信はPhase7-2-6で対応するため、今回は常に
    空文字が入る）
- `backend/app/routes/generation_routes.py`（修正）
  - `start_generation_job()`で`request.root_path`をusecaseに渡すよう変更
- `backend/app/dependencies.py`（修正）
  - プロセス全体のシングルトン`job_store`に、実ディレクトリを指す
    `GenerationJobRepository()`を結線
- テスト
  - `test_generation_job_repository.py`（新規）：`SectionJobStatus`・
    `datetime`・tuple系フィールドを含む、フル装備のジョブの保存→読み込み
    往復を検証
  - `test_job_store.py`（修正）：リポジトリ未設定時はディスクに一切書き込ま
    ないこと、設定時は書き込まれること、`get()`は常にインメモリの辞書から
    読むこと（リポジトリから読み直さないこと）を検証
  - `test_start_generation_job_usecase.py`（修正）：`run()`が各状態遷移で
    `job_store.save()`を呼ぶ回数（成功時4回、失敗時2回）を検証する
    `_SpyJobStore`を追加。`root_path`のデフォルト値・明示指定時の保持も検証

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **シリアライズをドメイン層のメソッドではなく、リポジトリ層の専用モジュール
  に置いた**：JSON形式の詳細（Enumの`.name`表現、tupleかlistかなど）は
  永続化という関心事であり、ドメイン層に持たせるとドメインクラスが
  「JSONにどう変換されるか」を知ることになってしまうため、責務を分離した。
- **`JobStore`のリポジトリ引数を`None`許容にした**：`RootPathHistoryRepository`
  のように実ディレクトリを指すデフォルト値にする案もあったが、それだと
  既存の`JobStore()`呼び出し（テストを含む多数の箇所）が黙って実ファイルへの
  書き込みを試みることになり、サンドボックスやテスト環境での予期しない
  副作用（書き込み権限、テスト間の汚染）につながる。`None`をデフォルトに
  することで、既存の呼び出し元・テストを一切変更せずに済み、本番配線のみ
  `dependencies.py`で明示的にリポジトリを渡す形にした。
- **`run()`にmark_*直後の`job_store.save()`呼び出しを追加した**：
  `JobStore`はジョブオブジェクトの参照を保持しているだけなので、インメモリ
  運用では直接ミューテーションだけで動いていた（`test_get_reflects_
  mutations_made_after_save`が示す通り）。しかし永続化を発火させるには
  「状態が変わった」という事実を`JobStore.save()`という単一の書き込み
  経路に明示的に伝える必要があるため、`run()`側にこの呼び出しを追加した。
  これにより「セクション単位」の書き込みは実現したが、「ブロック単位」
  （`on_block_generated`コールバック内）への拡張は次のPhaseに残している。
- **`test_generation_routes.py`にroot_pathのHTTPレベルテストを追加しな
  かった**：`GenerationJobStatusResponse`/`SectionJobStatusResponse`は
  どちらも`root_path`をレスポンスに含まないため、HTTP経由で検証しようと
  しても実質何もアサーションできない（Phase4-10で指摘を受けたプレース
  ホルダーテストと同じ穴になる）。`root_path`の値自体はusecase層の
  テストで確認済みなので、HTTP経由の確認はレスポンスに`root_path`が
  現れるようになるPhase7-2-4（履歴一覧API）に委ねることにした。

## ADR

今回はADRを書くレベルの設計判断はなし。
