# Phase2-9: ChatGptRepository実装

## 何を実装したか

- `backend/app/repositories/ai/chatgpt_repository.py`（新規）
  - `ChatGptRepository`：`openai`公式SDKのStructured Outputs
    （`response_format`に`type: "json_schema"`＋`strict: True`）で構造化
    出力を強制する。`strict: True`はスキーマ準拠のJSON文字列を保証するため、
    Claude実装と同様にGemini版の`json_repair.extract_cards_from_json`に
    相当する修復層は不要。ただし返ってくるのはあくまで文字列（Claudeの
    ように既にパース済みのdictではない）なので、`json.loads()`でのパースは
    引き続き必要。
  - リトライループはClaudeRepository・GeminiRepositoryと同じ形を独立して
    持つ。例外分類は`openai.AuthenticationError`／
    `openai.PermissionDeniedError`（即失敗）と`openai.RateLimitError`
    （指数バックオフ）という型付き例外で判定する（Claudeと全く同じ形）。
- `backend/app/repositories/ai/factory.py`（修正）
  - `_PROVIDER_API_KEY_ENV_VARS`に`"openai": "OPENAI_API_KEY"`を追加、
    `create()`に`"openai"`分岐を追加。これで3プロバイダー全ての分岐が
    揃った。
- `backend/pyproject.toml`（修正）：`openai>=1.50`を依存に追加。
- テスト
  - `tests/repositories/ai/test_chatgpt_repository.py`（新規）：Claude版と
    同じ観点（成功時／認証エラー×2種即失敗／レート制限バックオフ／未分類
    エラーのリトライ）に加え、`strict`モードでも万一不正なJSON文字列が
    返ってきた場合に他の一時的エラーと同様にリトライされることを確認する
    テストを追加（Geminiの「JSON修復失敗時のリトライ」テストに相当）。
  - `tests/repositories/ai/test_factory.py`（修正）：`"openai"`設定を
    `ChatGptRepository`にディスパッチするテスト、`OPENAI_API_KEY`未設定時に
    `MissingApiKeyError`となるテストを追加。既存の
    `test_unsupported_provider_raises`（`"chatgpt"`という消費者向け製品名は
    内部識別子ではないことを確認するテスト）はこのPhaseで初めて意味を持つ
    ようになった——Phase2-8時点では`"openai"`分岐自体が存在しなかったため
    `"chatgpt"`はもちろん`"openai"`も未対応だったが、このPhaseで`"openai"`が
    対応済みになったことで、「`"chatgpt"`は`"openai"`とは違う、対応外の
    文字列である」という区別を初めて実際に検証できるテストになった。

## 実装中に発見したバグ・問題点

- **`docker compose run`はGit管理と無関係に実際のファイルシステムから
  イメージをビルドする**という点を、Phase2-8のDocker確認時に再認識した。
  Phase2-9用に作業ツリー上に置いていた（まだ`git add`していない）
  `chatgpt_repository.py`／`test_chatgpt_repository.py`が、Phase2-8の
  `docker compose build`時にもそのままイメージへコピーされてしまい、
  `openai`未インストール（`pyproject.toml`にまだ追加していなかった）の
  状態で`pytest`が`test_chatgpt_repository.py`を収集して
  `ModuleNotFoundError: No module named 'openai'`となった。
  Gitのステージ状態と実際のビルド対象は別物であるため、Phase単位で
  厳密にDocker確認したい場合は、次のPhaseの分だけ作業ツリーに存在する
  ファイルを一時的に退避する必要がある、という運用上の教訓を得た
  （今回は該当2ファイルを一時的に別ディレクトリへ移動し、Phase2-8の
  確認後に元へ戻す形で対応した）。

## 大きな判断とその理由

- **Claudeと全く同じリトライループの構造をそのまま複製した**：
  Phase2-8で確定した「リトライループは3クラス独立で持つ（重複を許容する）」
  という方針（案α）に忠実に従った。ChatGptRepositoryとClaudeRepositoryの
  違いは実質的に「構造化出力の強制方式」と「生カードの取り出し方」の
  2箇所（前者はtool_choiceでのツール強制とdict取り出し、後者は
  response_formatでのjson_schema強制とJSON文字列のパース）のみで、
  リトライ・バックオフ・例外分類のロジック自体は意図的に完全に並行した
  構造にしている。

## ADR

今回はADRを書くレベルの設計判断はなし。
