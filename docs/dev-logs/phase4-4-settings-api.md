# Phase4-4: 設定API(プロバイダー/モデルのみ)

## 何を実装したか

- `backend/app/dependencies.py`（修正）
  - `get_settings_repository()`を追加。`SettingsRepository()`をリクエストのたびに新規生成して返す（他の依存関数と同様、状態をキャッシュしない）。テスト時は`app.dependency_overrides`で、`tmp_path`を指す`SettingsRepository`に差し替え可能。

- `backend/app/routes/schemas/settings.py`（新規）
  - `AiProviderSettingsResponse`（provider/model_name）：`GET`・`PUT`両方のレスポンス契約。
  - `UpdateAiProviderSettingsRequest`（provider/model_name）：`PUT`のリクエストボディ契約。

- `backend/app/routes/settings_routes.py`（新規）
  - `GET /settings`：`SettingsRepository.load()`をそのまま返す。
  - `PUT /settings`：リクエストから`AiProviderSettings`を構築し（空文字列などドメイン不変条件違反は`ValueError`→422に変換）、`SettingsRepository.save()`で永続化してから、保存内容をそのまま返す。
  - 科目リストUIやプロバイダーのホワイトリスト検証は持たせない。「対応していないプロバイダーが設定された」場合の実害は、実際に生成ジョブを開始する際（Phase4-3の`AiCardGeneratorFactory`）に500として顕在化する設計のため、設定APIの時点では単純な読み書きに徹する。

- `backend/app/main.py`（修正）
  - `settings_router`を`include_router`で登録。

- `backend/tests/routes/test_settings_routes.py`（新規）
  - `tmp_path`を指す`SettingsRepository`に差し替えたフィクスチャで、未保存時のデフォルト値取得、PUT→GETの往復、空`provider`／空`model_name`での422を検証。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **プロバイダーのホワイトリスト検証を設定APIに持たせなかった**：`AiCardGeneratorFactory`が既に「未対応プロバイダー」を`UnsupportedProviderError`として検出し、Phase4-3で500に変換する仕組みを持っている。設定APIの時点で同じ検証を重複させると、対応プロバイダーの一覧を2箇所で管理することになり不整合の元になるため、設定APIはドメインの不変条件（空文字列でないこと）のみをチェックする薄い読み書きに留めた。
- **`get_settings_repository()`もキャッシュしない**：Phase4-3の`get_ai_card_generator_repository()`と同じ考え方。設定はファイルベースであり状態を持つ必要がないため、リクエストごとに新規生成することで「保存直後の値が次のGETで即座に反映される」ことを保証する。

## ADR

今回はADRを書くレベルの設計判断はなし。
