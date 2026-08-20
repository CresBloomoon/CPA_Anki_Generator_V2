# Phase5-10: ルートパス履歴機能（バックエンド）

## 何を実装したか

- `backend/app/repositories/settings/root_path_history_repository.py`（新規）
  - `RootPathHistoryEntry`（`path`, `last_used_at`のfrozen dataclass）と`RootPathHistoryRepository`。
  - `load()`：JSONファイル（デフォルトは`backend/root_path_history.json`）が存在しなければ空リストを返す。
  - `add_or_update(root_path)`：MRU（Most Recently Used）方式。同一`path`の既存エントリがあれば
    一旦取り除き、新しいタイムスタンプで先頭に挿入し直す（＝重複させず「最近使った順」に並べ替える）。
    保存前に先頭5件（`_MAX_ENTRIES`）へ切り詰める。並び順の正とするのは常に**リスト内の位置**であり、
    `last_used_at`は表示用の情報でしかない（保存時にしか使わず、読み込み時に日時としてパースし直すことは
    一切しない）。
- `backend/app/routes/schemas/root_path_history.py`（新規）：`RootPathHistoryEntryResponse`／
  `RootPathHistoryResponse`のPydanticスキーマ。
- `backend/app/routes/root_path_history_routes.py`（新規）：`GET /root-path-history`。
  リポジトリの`load()`結果をそのままレスポンスに変換するだけの薄いルート。
- `backend/app/dependencies.py`（修正）：`get_root_path_history_repository()`を追加
  （`get_settings_repository()`と同様、キャッシュなしで毎回新規インスタンスを返す）。
- `backend/app/main.py`（修正）：`root_path_history_router`を登録。
- `backend/app/routes/pdf_routes.py`（修正）：`scan_pdfs`に
  `root_path_history_repository: RootPathHistoryRepository = Depends(...)`を追加し、
  スキャン成功後（`usecase.execute`の例外処理を通過した後）に
  `DeckPath.from_string(request.root_path).joined()`で正規化した値を`add_or_update`に渡すようにした。
- テスト
  - `backend/tests/repositories/settings/test_root_path_history_repository.py`（新規、6件）：
    ファイル未作成時に空リスト／新規追加は先頭へ／既存パスの再追加は重複させず先頭に移動／
    6件目追加で最古の1件が切り捨てられる／親ディレクトリが無くても自動作成される／
    `last_used_at`が空文字でないこと、を確認。
  - `backend/tests/routes/test_root_path_history_routes.py`（新規、2件）：未保存時は空リスト／
    保存済みエントリが最新順で返る。
  - `backend/tests/routes/test_pdf_routes.py`（修正）：`client`フィクスチャが
    `get_root_path_history_repository`も`tmp_path`ベースのインスタンスでオーバーライドするよう修正
    （後述）。`/scan`成功時に正規化済みのルートパスが履歴に記録されることを確認する
    `test_scan_success_records_the_normalized_root_path_in_history`を追加。

## 実装中に発見したバグ・問題点

- `test_pdf_routes.py`の`client`フィクスチャが、`get_pdf_store`のみをオーバーライドしていて
  `get_root_path_history_repository`をオーバーライドしていなかった。このままだと`/scan`を叩く既存の
  テスト（トップレベル区切り文字の正規化テスト等）が実際に`backend/root_path_history.json`（本番用の
  実ファイル）へ書き込んでしまい、テスト実行のたびにリポジトリ直下のファイルが汚染される状態になって
  いた。実装時に自分で気づいて修正し、`tmp_path`ベースの`RootPathHistoryRepository`をDIで差し込むように
  直した。

## 大きな判断とその理由

- **ドメイン層への追加は見送った**：ルートパス履歴は「ユーザーの入力補助のためのUI向け情報」であり、
  ドメインの不変条件やビジネスルールを表すものではない（`Section`や`DeckPath`のような値オブジェクトとは
  性質が異なる）。設定値の永続化という点で`SettingsRepository`と役割が近いため、
  `repositories/settings/`配下に置くのが自然と判断した。
- **保存（`add_or_update`呼び出し）はUsecase層ではなくroutes層（`pdf_routes.py`）で行った**：
  `ScanPdfStructureUsecase`はあくまで「PDFを解析してSectionを組み立てる」責務に閉じており、
  「ユーザーがどのルートパスを最近使ったか」を記録するのはHTTPリクエスト固有の関心事（UI向けの
  副作用）と捉えた。Usecaseに混ぜるとテスト時のフェイクリポジトリ差し替えが1つ増え、Usecase自体の
  責務も曖昧になるため、ルート側で明示的に呼び出す形にした。
- **保存する値は`request.root_path`そのものではなく、`DeckPath.from_string(...).joined()`で正規化した
  canonicalな形にした**：`DeckPath.from_string()`は末尾の`"::"`や前後の空白、空セグメントを既に
  取り除く役割を持っている（Phase5-3のバグ修正で導入済み）。履歴にはこの正規化後の値を記録することで、
  「見た目は同じルートパスなのに末尾の`"::"`の有無で別エントリとして重複表示される」事態を防いだ。

## ADR

今回はADRを書くレベルの設計判断はなし。
