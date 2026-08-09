# Phase4-1: PDFアップロード/スキャンAPI

## 何を実装したか

- `backend/app/dependencies.py`（新規）
  - `PdfStore`のプロセス内シングルトンインスタンスと、それを返すFastAPI依存関数`get_pdf_store()`を定義。ルートハンドラーはこの関数を`Depends()`で受け取ることで、テスト時に`app.dependency_overrides`経由でストアを差し替えられる。

- `backend/app/routes/schemas/__init__.py`（新規）
  - `routes/schemas`パッケージの初期化ファイル。中身はなし。

- `backend/app/routes/schemas/pdf.py`（新規）
  - `/pdfs`・`/scan`エンドポイントの入出力契約をPydanticモデルとして定義：`UploadPdfResponse`（アップロード結果）、`ScanRequest`（スキャン対象ファイル名リスト＋ルートパス）、`SectionScanResult`（1節分のスキャン結果）、`ScanResponse`（節一覧＋警告一覧）。ドメインエンティティ（`Section`等）とは別に持つことで、APIのシリアライズ形式とドメインモデルの変更を独立させる。

- `backend/app/routes/pdf_routes.py`（新規）
  - `POST /pdfs`：アップロードされたファイルを`PdfStore`に保存し、ファイル名とサイズを返す。ファイル名が空の場合は400を返す自前バリデーションを持つ。
  - `POST /scan`：指定された複数のソースファイルを`PdfStore`から取得し、`ScanPdfStructureUsecase`（Phase3-1）に委譲して節一覧を取得、JSONへ変換して返す。未アップロードのファイルが指定された場合は404、PDF解析に失敗した場合は422を返す。
  - どちらのハンドラーもUsecase層・リポジトリ層への薄い委譲のみを行い、ビジネスロジックは持たない。

- `backend/app/main.py`（修正）
  - `pdf_router`を`include_router`で登録。

- `backend/pyproject.toml`（修正）
  - `python-multipart`を本番依存に追加（FastAPIのファイルアップロード処理に必須）。
  - `httpx`を`dev`エクストラに追加（`TestClient`が内部で利用するため）。

- `backend/tests/routes/test_pdf_routes.py`（新規）
  - `TestClient`＋`app.dependency_overrides`でPDFストアをテストごとに独立させたフィクスチャ。
  - `POST /pdfs`の正常系、`POST /scan`の正常系（階層がdeck_pathに反映されること）、未アップロードファイル指定時の404、不正PDFバイト列指定時の422、空ファイル名アップロード時の400を検証。

## 実装中に発見したバグ・問題点

- **`test_upload_without_filename_returns_400`が422で失敗した件**：Docker実機での初回pytest実行で、空ファイル名アップロードを検証するテストが期待した400ではなく422を返す事象が発生した。まーくんの指示のもと、推測せずに以下を実機調査した。
  1. 実際のレスポンスボディを確認したところ、`{"detail": [{"type": "value_error", "loc": ["body", "file"], "msg": "Expected UploadFile, received: <class 'str'>", ...}]}`というFastAPI標準のバリデーションエラー形式だった。
  2. httpxが実際に生成する生のmultipartボディを確認したところ、`files={"file": ("", ...)}`のように`filename=""`（空文字列）を渡すと、httpxは`Content-Disposition`ヘッダーから`filename`属性自体を省略していることが分かった（空文字列がfalsy値として扱われている模様）。
  3. Starlette/FastAPIのmultipartパーサーは、パートをファイルとして扱うかどうかを`filename`属性の**有無**で判定するため、属性が無いパートは`str`型の通常フィールドとみなされ、`file: UploadFile`という型注釈との不一致でFastAPI自身が422を返していた（自前の`if not file.filename`バリデーションには到達していなかった）。
  4. さらに、実際のブラウザは`<input type="file">`が未選択のままフォーム送信されると、`filename`属性自体は残したまま値だけが空文字列のパートを送信する（WHATWG HTML標準の仕様）ことを確認。この事実により「空ファイル名アップロード」というシナリオ自体は実運用で起こり得るものであり、テストケースを削除する理由にはならないと判断した。
  5. 生のmultipartボディを手組みして`filename=""`を明示的に残した状態で送信するリクエストを実機で試したところ、期待通り400＋`"filename is required"`が返ることを確認した。

  **対処**：テストシナリオ自体は変更せず、リクエストの組み立て方法をhttpxの`files={}`簡易記法から、生のmultipartボディを手組みする方式に書き換えた。これにより実際のブラウザが送信するリクエストを正確に再現しつつ、ルート実装の自前バリデーションを検証できるようにした。実装（`pdf_routes.py`の`if not file.filename`チェック）自体に問題はなく、修正はテストコード側のみ。

- **StarletteDeprecationWarning（`httpx`を`starlette.testclient`と併用する非推奨警告）**：pytest実行時に1件の警告が出力されたが、`starlette.testclient`モジュール自体が発しているものであり、こちらのテストコードやアプリケーションコードには起因しない。実害もないため、現時点では対応不要と判断し放置する。

## 大きな判断とその理由

- **ルート層は薄く保つ**：`pdf_routes.py`のハンドラーはUsecase/リポジトリへの委譲とHTTPステータスへの変換のみを行い、ビジネスロジックを一切持たない。責務の分離をコメントではなく層構造そのもので表現するという方針に沿ったもの。
- **PdfStoreはFastAPIの`Depends()`経由で注入**：シングルトンをモジュールグローバルに直接置くのではなく`Depends(get_pdf_store)`を挟むことで、テスト時に`app.dependency_overrides`で差し替え可能にし、テスト間の状態漏れを防いだ。
- **空ファイル名バリデーションのテストは「削除」ではなく「テストの組み立て方法の修正」で解決**：httpx側のエンコーディング仕様とブラウザの実際の仕様が異なるという事実が判明した時点で、「httpx経由では再現不可能だから削除する」という判断は早計であり、実運用で起こり得るシナリオを検証し続けるために、テスト側の実装方法（生のmultipartボディ手組み）を見直す方針を選んだ。

## ADR

今回はADRを書くレベルの設計判断はなし（既存のPhase3-1のUsecase設計をそのままルート層から呼び出しただけであり、アーキテクチャ上の新しい判断は発生していない）。
