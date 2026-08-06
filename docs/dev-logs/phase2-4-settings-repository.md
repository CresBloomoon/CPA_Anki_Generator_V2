# Phase2-4: 設定リポジトリ（プロバイダー／モデル選択）

## 実装したもの

- `backend/app/repositories/settings/settings_repository.py`
  - `AiProviderSettings`：`provider`／`model_name`の2フィールドのみを持つ値オブジェクト
    （空文字列は拒否）。科目リスト・デッキルートテンプレート等は依頼書のスコープ外と
    既に決定済みのため含めていない。
  - `SettingsRepository`：`backend/settings.json`（デフォルトパス、コンストラクタで
    差し替え可能）への読み書きのみを行う薄いリポジトリ。ファイルが存在しない場合は
    デフォルト値（`provider="gemini"`, `model_name="gemini-2.5-pro"`）を返す。
- `backend/tests/repositories/settings/test_settings_repository.py`：バリデーション、
  ファイル未存在時のデフォルト、保存→読込の往復、親ディレクトリの自動作成、外部で
  書かれたファイルの読込を検証（6ケース）。
- `.gitignore`に`backend/settings.json`を追加（初回保存時に生成される実行時ファイルで
  あり、ソース管理対象外とするため）。

## 設計判断

- `settings.json`のパスはコンストラクタ引数で注入可能にした。デフォルトは
  `backend/settings.json`だが、テストでは`tmp_path`に差し替えて実ファイルシステムへの
  副作用なしに検証できる。
- このリポジトリはPython標準ライブラリ（`json`／`dataclasses`／`pathlib`）のみに依存し、
  PyMuPDFやgoogle-genaiのような外部SDKを必要としない。

## 実装中に発見したバグ・問題点

特になし。

## 動作確認

- 外部依存が無いため、サンドボックス内で`tempfile.TemporaryDirectory()`を使い、
  テストファイルと同一のロジックを直接実行して全6ケースを確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`80 passed in 6.08s`を確認済み
  （Phase2-3完了時点の74件＋今回の6件）。

## ADR

小規模な実装であり、ADRを起票するほどの分岐ではないと判断した。
