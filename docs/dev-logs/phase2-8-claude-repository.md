# Phase2-8: ClaudeRepository実装

## 何を実装したか

- `backend/app/repositories/ai/card_content_mapper.py`（新規）
  - `to_card_content_item(raw_card: dict) -> CardContentItem`。これまで
    `gemini_repository.py`内に`_to_card_content_item`としてプライベートに
    定義されていた変換ロジックを、Gemini／Claude／ChatGPTの3リポジトリ共通の
    公開関数として切り出した。この変換自体にはプロバイダー固有の分岐が一切
    ないため、「リトライループは3クラス独立で持つ（重複を許容する）」という
    今回の設計判断（案α）とは別問題として、素直にDRY化した。
- `backend/app/repositories/ai/gemini_repository.py`（修正）
  - 上記の共通関数を使うようリファクタ。`CardContentItem`の直接importも
    不要になったため削除。挙動に変更はない。
- `backend/app/repositories/ai/claude_repository.py`（新規）
  - `ClaudeRepository`：`anthropic`公式SDKのtool useで構造化出力を強制する。
    カード配列を受け取る単一のツール（`record_cards`）をJSON Schemaで定義し、
    `tool_choice`でそのツールの呼び出しを強制する。返ってくる
    `tool_use.input`は既にSDKがパース済みのdictなので、Gemini版の
    `json_repair.extract_cards_from_json`に相当する修復層は不要。
  - リトライループはGeminiRepositoryと同じ形（試行→例外分類→バックオフ→
    リトライ）を独立して持つ。例外分類はGeminiの文字列マーカー判定
    （`"429"`等が含まれるか）とは異なり、`anthropic.AuthenticationError`／
    `anthropic.PermissionDeniedError`（即失敗、リトライしない）と
    `anthropic.RateLimitError`（指数バックオフ）という型付き例外で判定する。
- `backend/app/repositories/ai/factory.py`（修正）
  - `_PROVIDER_API_KEY_ENV_VARS`に`"claude": "CLAUDE_API_KEY"`を追加、
    `create()`に`"claude"`分岐を追加。
- `backend/pyproject.toml`（修正）：`anthropic>=0.40`を依存に追加。
- テスト
  - `tests/repositories/ai/test_card_content_mapper.py`（新規）：共通変換
    関数の単体テスト（全フィールドのマッピング、欠損フィールドのデフォルト値、
    TAGSのカンマ区切り文字列分割）。
  - `tests/repositories/ai/test_claude_repository.py`（新規）：成功時／
    認証エラー（`AuthenticationError`・`PermissionDeniedError`、いずれも
    リトライなし即失敗）／レート制限（`RateLimitError`、指数バックオフ）／
    未分類エラー（一律の遅延でリトライ→上限到達で例外）／tool_useブロックが
    レスポンスに含まれない防御的なケース（他の一時的エラーと同様にリトライ）。
  - `tests/repositories/ai/test_factory.py`（修正）：`"claude"`設定を
    `ClaudeRepository`にディスパッチするテスト、`CLAUDE_API_KEY`未設定時に
    `MissingApiKeyError`となるテストを追加。

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **`anthropic.AuthenticationError`等の型付き例外の実際のコンストラクタ
  引数を、サンドボックスでは確認できなかった**（`anthropic`パッケージが
  未インストールのため）。CLAUDE.mdの「サンドボックスで検証できない依存
  ライブラリの扱い」に従い、`backend/tmp_samples/investigate_sdk_exceptions.py`
  という調査スクリプトを作成し、まーくんにDocker環境での実行を依頼した。
  結果、`SomeError("message", response=httpx.Response(...), body=None)`と
  いう形で構築できることが確認できたため、テストコードのフェイク例外
  送出にこの形をそのまま使用した。調査スクリプトは役目を終えたため削除済み。
  - なお調査時、`docker compose run`だけでは`tmp_samples/`ディレクトリが
    イメージに含まれず（`Dockerfile`が`app/`と`tests/`のみをCOPYする構成の
    ため）実行できない問題が見つかった。`Dockerfile`自体を変更する
    （`tmp_samples/`をCOPY対象に恒久的に加える）のではなく、
    `docker compose run --rm -v "$(pwd)/backend/tmp_samples:/app/tmp_samples" ...`
    という1回限りのボリュームマウントで対応した。`tmp_samples/`は
    `.gitignore`対象で中身が空の環境もあり得るため、`Dockerfile`の
    `COPY`対象に含めてしまうと空ディレクトリでビルドが壊れるリスクがある
    ことと、そもそも「調査が終わったら痕跡を残さず削除する」という
    運用ルールの精神に合わないと判断したため。
- **`raw_card dict → CardContentItem`の変換ロジックを共通関数として
  切り出した**：Claude実装にあたり、Gemini用に書かれていたこの変換を
  そのままコピーするとClaude／ChatGPTの2箇所で重複することになる。この
  変換自体はプロバイダーごとの構造化出力の強制方式（JSON文字列のパース／
  修復か、既にパース済みのdictか）とは無関係な純粋なデータ変換であり、
  分岐も一切持たないため、「リトライループの重複は許容する」という
  Phase2-8着手前の設計判断とは別の問題として、素直に`card_content_mapper.py`
  へ切り出した。
- **例外分類の粒度**：Geminiの`_is_auth_error`は`"401"/"403"/
  "PERMISSION_DENIED"/"UNAUTHENTICATED"/"API_KEY_INVALID"`という複数の
  文字列マーカーを1つの「認証エラー」カテゴリとして扱っていたが、Claudeでは
  SDKが`AuthenticationError`（401）と`PermissionDeniedError`（403）を
  別クラスとして提供している。どちらもリトライしても直らない点は同じ
  なので、`except (AuthenticationError, PermissionDeniedError)`と1つの
  節でまとめて即失敗させることにし、Geminiの「認証エラーは1カテゴリ」
  という扱い方と実質的に揃えた。

## ADR

今回はADRを書くレベルの設計判断はなし。
