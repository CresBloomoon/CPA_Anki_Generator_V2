# Phase0-1: バックエンド最小骨格

## 実装したもの

- `backend/app/main.py` — FastAPIアプリのエントリポイント。`GET /health` のみを持つ
  （`{"status": "ok"}` を返す）。以降のPhaseで各層の実装が進むまでは、これ以外のエンドポイントは
  意図的に置いていない。
- `backend/app/{routes,usecases,domain}/__init__.py` — 各レイヤーの空パッケージ。実体は後続Phase
  （Step1〜4）で追加する。
- `backend/app/repositories/{ai,pdf,anki,jobs,settings}/__init__.py` — リポジトリ層のサブパッケージ。
  依頼書の4層構造（routes → usecases → repositories → domain）に対応させたディレクトリ配置。
- `backend/pyproject.toml` — 依存は`fastapi`と`uvicorn[standard]`のみ。`hatchling`をビルド
  バックエンドにして`app`パッケージをホイール化し、`pip install .`一発でアプリと依存を導入できる
  ようにした。
- `backend/Dockerfile` — `python:3.12-slim`ベース。`pyproject.toml`と`app/`をコピーして
  `pip install .`、`uvicorn app.main:app`で起動（ポート8000）。
- ルート直下 `.gitignore` — `__pycache__`/`.venv`/`node_modules`/`.env`（`.env.example`は除外
  対象から除く）などを追加。

## 設計判断

- 依存管理は`requirements.txt`ではなく`pyproject.toml`＋`hatchling`を採用した。Dockerfile側は
  `pip install -r requirements.txt`ではなく`pip install .`のみで済み、依存とパッケージ配置
  （`packages = ["app"]`）を1ファイルで完結させられるため。
- Dockerイメージは`python:3.12-slim`を選択。特定のPyMuPDF/genanki等のバージョン制約は今後の
  Phaseで判明するため、現時点ではバージョン固定はせず`>=`指定に留めている。

## 動作確認

- 開発者側の実機（Docker利用可能な環境）で `docker build` → `docker run` → `curl
  http://localhost:8000/health` を実施し、`{"status":"ok"}`（200 OK）を確認済み。
- 実装時のサンドボックス環境にはDocker／pipが存在しなかったため、Claude Code側では
  `python3 -m py_compile app/main.py`によるシンタックスチェックのみ実施し、実際の起動確認は
  開発者に依頼した。

## 発見した問題点

特になし。

## ADR

今回の判断（`pyproject.toml`+`hatchling`の採用、`python:3.12-slim`の選定）はいずれも小規模な
技術選定であり、ADRを起票するほどの分岐ではないと判断した。
