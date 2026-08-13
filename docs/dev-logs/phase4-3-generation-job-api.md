# Phase4-3: 生成ジョブAPI(開始/進捗ポーリング/ダウンロード)

## 何を実装したか

- `backend/app/domain/generation_job.py`（修正）
  - `GenerationJob`に`additional_prompt: str = ""`を追加。1ジョブ＝1回の生成リクエストという単位に合わせ、セクションごとではなくジョブ単位で1つ保持する。

- `backend/app/usecases/generate_cards_for_section_usecase.py`（修正）
  - `execute(section, pdf_bytes, additional_prompt="")`：受け取った`additional_prompt`をそのまま`PromptContext`に渡すよう配線。`PromptBuilder`は既に`additional_prompt`を処理できる実装だったため（Phase2-2で先行実装済み）、変更はこの1箇所のみ。

- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `execute(sections, additional_prompt="")`：`GenerationJob`生成時にセット。
  - `run()`：各セクション呼び出し時に`job.additional_prompt`を渡す。

- `backend/app/dependencies.py`（修正）
  - `job_store`のプロセス内シングルトンと`get_job_store()`を追加。
  - `get_ai_card_generator_repository()`：`SettingsRepository().load()`で**リクエストのたびに**設定を読み直し、`AiCardGeneratorFactory().create()`でAIリポジトリを生成する。Phase4-4で設定変更APIができた際、バックエンド再起動なしに反映されるようにするため、キャッシュはしない。
  - `_build_ai_repository(settings)`：上記から設定読み込み・HTTPへの変換ロジックだけを切り出した純粋関数。`MissingApiKeyError`・`UnsupportedProviderError`を`HTTPException(status_code=500)`に変換する（クライアントの入力ミスではなくサーバー側の設定不備のため500）。実際のsettings.jsonファイルやFastAPIの依存解決を経由せずに単体テストできるよう、あえて`get_ai_card_generator_repository()`本体とは別関数に分離した。

- `backend/app/routes/schemas/generation.py`（修正）
  - `StartGenerationJobResponse`（job_id）、`SectionJobStatusResponse`（title/status/card_count/error_message）、`GenerationJobStatusResponse`（job_id/is_complete/section_jobs）を追加。ステータスレスポンスの形は**暫定案**であることをコメントで明記（Phase5でフロントエンドと実際に繋いだ結果、情報の過不足が見つかれば変更する前提。まーくんとの合意事項）。

- `backend/app/routes/generation_routes.py`（新規）
  - `POST /generation-jobs`：`StartGenerationRequest`から`Section`一覧を組み立て（`PageRange`・`DeckPath.from_string`経由）、`StartGenerationJobUsecase`を起動し`job_id`を返す。`Section`/`PageRange`/`DeckPath`のドメイン不変条件違反（例：空のdeck_path）は`ValueError`を捕捉して422に変換。
  - `GET /generation-jobs/{job_id}`：`GetGenerationJobStatusUsecase`を呼び、暫定のステータスレスポンスに変換。未知の`job_id`は404。
  - `GET /generation-jobs/{job_id}/download`：`BuildAnkiPackageUsecase`を呼び、`.apkg`バイト列を`Content-Disposition: attachment`で返す。完了状態に応じてファイル名を`generated.apkg`／`generated_partial.apkg`で出し分け。未知の`job_id`は404。

- `backend/app/main.py`（修正）
  - `generation_router`を`include_router`で登録。

- テスト
  - `backend/tests/domain/test_generation_job.py`：`additional_prompt`のデフォルト値・明示指定を検証。
  - `backend/tests/usecases/test_generate_cards_for_section_usecase.py`：`additional_prompt`が`PromptContext`まで伝わること、デフォルトが空文字であることを検証。
  - `backend/tests/usecases/test_start_generation_job_usecase.py`：ジョブの`additional_prompt`が全セクション呼び出しに転送されること、`execute()`経由でジョブに正しく保存されることを検証。
  - `backend/tests/test_dependencies.py`（新規）：`_build_ai_repository()`単体で、APIキー未設定／未対応プロバイダーがどちらも`HTTPException(500)`になること、正常系で例外が出ないことを検証。
  - `backend/tests/routes/test_generation_routes.py`（新規）：`TestClient`＋`app.dependency_overrides`（pdf_store/job_store/AIリポジトリをすべてフェイクに差し替え）で、生成ジョブ開始→ポーリングでDONE確認→ダウンロードで`.apkg`取得、という一連の流れと、不正なdeck_path・未知のjob_idでのエラー系を検証。

## 実装中に発見したバグ・問題点

なし。ただしテスト実装中に、`PageRange`の`end_page`セマンティクス（`end_page`は排他的で、`start_page == end_page`だと抽出ページ数が0になる）を再確認し、1ページ分のテキストを実際に抽出させたいテストでは`end_page=None`（open-ended）を使う必要があると気づいた。これは`extract_text_from_range`の既存実装（Phase2-1）通りの挙動であり、実装側の不具合ではない。

## 大きな判断とその理由

- **AIリポジトリの構築を`Depends()`経由の差し替え可能な依存にした**：ルート内で直接`AiCardGeneratorFactory().create(...)`を呼ぶのではなく、`get_ai_card_generator_repository()`という依存関数を挟むことで、テスト時にフェイクのAIリポジトリへ差し替え可能にした。これにより`POST /generation-jobs`のルートテストが実際のGemini APIキーやネットワーク接続なしで完結する。
- **設定はリクエストのたびに読み直す（キャッシュしない）**：まーくんとの事前合意通り。Phase4-4で設定変更APIが実装された際、バックエンド再起動なしに新しいプロバイダー/モデル設定が次回の生成ジョブから反映されるようにするため。
- **APIキー未設定・未対応プロバイダーは500**：まーくんとの事前合意通り。クライアントの入力ミスではなくサーバー側の設定不備であるため。
- **ステータスレスポンスの形は暫定案という位置づけ**：まーくんとの事前合意通り、Phase5でフロントエンドと実際に繋いでみるまでは確定させない。コード側にもその旨をコメントで明記した。
- **`Section`構築時の`ValueError`を422に変換**：`/scan`ルート（Phase4-1）が`PdfParsingError`を422に変換しているのと同じ考え方で、ドメイン層の不変条件違反をクライアントへの422として一貫して扱う。

## ADR

今回はADRを書くレベルの設計判断はなし。
