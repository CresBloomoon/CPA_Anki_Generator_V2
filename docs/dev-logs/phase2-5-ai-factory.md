# Phase2-5: AI Repository Factory

## 実装したもの

- `backend/app/repositories/ai/factory.py`：`AiCardGeneratorFactory.create(settings:
  AiProviderSettings) -> AiCardGeneratorRepository`
  - `_PROVIDER_API_KEY_ENV_VARS`（プロバイダー名→`.env`環境変数名のマッピング。現時点は
    `{"gemini": "GEMINI_API_KEY"}`のみ）を持ち、`settings.provider`で分岐して対応する
    APIキーを環境変数から読み、`GeminiRepository`を構築する。
  - Factoryは`SettingsRepository`（`settings.json`の永続化）には依存しない。設定の
    読み込みは呼び出し元（Usecase層）の責務とし、Factoryは受け取った`AiProviderSettings`
    から具象リポジトリを組み立てるだけの純粋な変換ロジックに徹する（詳細は「設計判断」
    参照）。
  - 未対応のプロバイダーは`UnsupportedProviderError`、対応する環境変数が未設定の場合は
    `MissingApiKeyError`を送出する。
- `backend/tests/repositories/ai/test_factory.py`：フェイクの`GeminiRepository`への
  正しいディスパッチ（コンストラクタ引数の検証込み）、実`GeminiRepository`インスタンスが
  返ること、APIキー未設定時のエラー、未対応プロバイダー時のエラーを検証（4ケース）。

## 設計判断

実装前にユーザーと相談し、以下の2案を比較した。

- 案A：`create(settings: AiProviderSettings)`——Factoryは設定を引数で受け取るだけで、
  `SettingsRepository`への依存を持たない
- 案B：`create()`——Factory自身が`SettingsRepository`を保持し、内部で`load()`を呼ぶ

**案Aを採用した。** 理由は、Factory単体のテストがファイルI/O（`SettingsRepository`の
フェイクや一時ファイル）に一切触れず、`AiProviderSettings`オブジェクトを直接渡すだけで
完結するため。設定の読み込みタイミングについては、キャッシュはせず「`create()`が
呼ばれる（＝ジョブ開始時）たびに呼び出し元が`SettingsRepository.load()`を呼び直す」
方針で合意した。`create()`自体はジョブ開始時に1回しか呼ばれない想定のため、都度
ファイルを読み直すコストは無視できるほど小さく、逆にキャッシュすると「Phase5-5の
設定UIで変更しても次のジョブに反映されない（要再起動）」という直感に反する挙動に
なるため、キャッシュしない方針とした。

一方、APIキーの環境変数読み取りは、Factory内部で行うこととした（依頼書の元々の
`create(settings) -> AiCardGeneratorRepository`という単一引数のインターフェース
イメージに合わせた）。`settings.json`（非機密の設定）と`.env`（機密のAPIキー）は
情報源としての性質が異なり、後者はリポジトリ抽象を介さず`os.environ`から直接読む
軽量な操作として扱う。

## 実装中に発見したバグ・問題点

特になし。

## 動作確認

- `google-genai`が未インストールの環境だったため、SDKをスタブ化した上でテストファイルと
  同一のロジックを手動実行し、全5アサーションを確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`84 passed in 6.09s`を確認済み
  （Phase2-4完了時点の80件＋今回の4件）。

## ADR

Factoryの設定受け渡し方式（案A採用）は実装前にユーザーと協議の上で決定した判断だが、
影響範囲がPhase2-5単体に閉じており、ADRを起票するほどの分岐ではないと判断した。
