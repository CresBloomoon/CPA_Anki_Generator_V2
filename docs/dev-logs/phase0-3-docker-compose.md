# Phase0-3: Docker Compose結線 + .env.example

## 実装したもの

- `.env.example`（リポジトリルート直下）：`GEMINI_API_KEY=`／`CLAUDE_API_KEY=`／
  `OPENAI_API_KEY=`のみ、値は空。セットアップ時に何を用意すればよいかが分かるようにした。
- `docker-compose.yml`（リポジトリルート直下）：`backend`／`frontend`の2サービスに分離。
  - `backend`：`./backend`をビルド、`env_file: .env`でルートの`.env`を読込、`8000:8000`
  - `frontend`：`./frontend`をビルド、`5173:5173`
  - 現行のCompose Specでは`version:`キーは非推奨のため付けていない

## 設計判断

- `.env`はリポジトリルート直下に置く方針（CLAUDE.mdのPhase0-3決定事項通り）。旧リポジトリは
  `app/.env`だったが、V2はcompose起点で管理する方がシンプルなため。
- ホットリロード用のvolumeマウント（`./backend:/app`等）は今回は入れていない。Phase0-3の
  スコープを「Compose結線＋`.env.example`」に留め、開発体験の改善は必要になった時点で
  別途対応する。

## 動作確認

- 開発者側の実機で`cp .env.example .env`の上、`docker compose up --build`を実施し、両コンテナ
  が正常起動することを確認。
  - `curl http://localhost:8000/health` → `{"status":"ok"}`
  - `curl http://localhost:5173/` → `<title>CPA Anki Generator V2</title>`を含むHTML
- 実装時のサンドボックス環境にはDockerが存在しないため、`docker compose up`自体の検証は
  開発者に依頼した。

## 発見した問題点

- 動作確認時、Phase0-2で`docker run --rm`により起動したままだった旧`cpa-anki-frontend`
  コンテナがポート5173を占有しており、`docker compose up`が失敗する事象が発生した。
  コードやcompose設定自体の不具合ではなく、Phase0-2の手動検証で使った一時コンテナの停止
  忘れが原因。開発者側で該当コンテナを`docker stop`してから再実行し解消した。以降、
  `docker run --rm`で一時的に起動したコンテナは動作確認後に必ず停止する運用とする。

## ADR

`.env`の配置場所（ルート直下）とvolumeマウント見送りはいずれも小規模な判断であり、ADRを
起票するほどの分岐ではないと判断した。
