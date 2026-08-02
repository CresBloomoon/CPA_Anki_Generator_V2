# 実装依頼：CPA Anki自動生成アプリ（フルスクラッチ再構築）

## 背景・対象リポジトリ

- 既存リポジトリ：`CresBloomoon/CPA_Anki_Generator`（Python/Streamlit + Gemini API）
  - Antigravity + Geminiを使ったバイブコーディング初挑戦時に作成したもので、つぎはぎ構造になっている
  - `st.data_editor`のキャッシュ不整合バグ（セル編集1回目でリバートする挙動）に対して、`.copy()`渡し＋`sections_df`/`sections_df_latest`の二重ステート管理という力技で回避しており、この構造自体が保守性を下げている
  - このリポジトリは**参照専用**として扱い、内容は変更しない（既存カードテンプレートの4段構成・プロンプト内容の参考元として使う）
- 新規リポジトリ `CPA_Anki_Generator_V2` を作成し、フロントエンド・バックエンドともにフルスクラッチで再構築する
- 既存リポジトリは `/mnt/files/repos/CPA_Anki_Generator` に既にclone済み。参照専用として扱い、内容は変更しない

## 事前準備（Claude Code起動前）

- 参照元の既存リポジトリは、既にコンテナ内 `/workspace/CPA_Anki_Generator` にクローン済み（ホスト側の実体は `/mnt/files/repos/CPA_Anki_Generator`）
- 新規リポジトリ `CPA_Anki_Generator_V2` も、GitHub上に作成の上、同じ `/workspace/` 配下にcloneし、そのディレクトリでClaude Codeを起動する
- 起動時、参照用の既存リポジトリを `--add-dir` で追加すること：
  ```bash
  cd /workspace/CPA_Anki_Generator_V2
  claude --add-dir /workspace/CPA_Anki_Generator
  ```
- `CPA_Anki_Generator`（旧・V2でない方）は参照専用として扱うこと。実装・編集はすべて新規リポジトリ（`CPA_Anki_Generator_V2`）側で行い、参照元の内容は変更しない
- 参照する際は、特に以下を踏襲元として使うこと：
  - `app/card_templates/` 配下（HTML/CSS、4段構成の実物）
  - `app/prompts/` 配下（`project_constitution.md` / `anki_generation.md`）
  - `app/main.py` の `st.data_editor` 部分（同じ轍を踏まないための反面教師として）

## 開発者について（実装スタイルの前提）

- C#でのテスト駆動開発・ドメイン駆動設計の実務経験5年。Web開発（TypeScript/React/FastAPI）は初心者
- コードはコメントで説明するのではなく、関数・クラス・コンポーネントの責務を細かく分割することで可読性を確保すること
- 4層構造（routes → usecases → repositories → domain）の流儀を踏襲し、新規実装もこのパターンに厳密に従うこと（`CresBloomoon/CPA-Dashboard-Core`と同じ設計思想）
- 依頼者自身がコードを読んで理解できることを重視する
- 推測でのトラブルシューティングは行わないこと。エラー発生時は原因特定に必要なログ・ファイル・実行環境の情報を具体的に確認してから対処すること
- 開発・PC環境を汚すことを極端に嫌う。構築はDocker / Docker Composeを優先し、ホストOSへの直接インストールは避けること

## 概念フレームワーク

- 目的：公認会計士試験のテキストPDFから、Anki用フラッシュカードを自動生成し、手動でのカード作成の手間を最小化すること
- 満たすべき特性：
  - 正確性：AI生成カードにPDF実データ（ページコード等）が正しく反映されている
  - 拡張性：利用するAIプロバイダー・モデルを将来的に自由に切り替えられる
  - 実用性：完全自動を目指さず、人間が確認・微調整できる前提のUIにする

## 機能要件

### 1. PDF解析・構成確認
- PDFをアップロードすると、章・節・タイトル・開始ページを自動検出する
- 検出結果は人間が確認・修正できるテーブルUIで表示する
- テーブルはシンプルな`<table>`＋React state構成とする（TanStack Table等の高機能ライブラリは現時点では不要、行数が増えて重くなった場合に再検討）
- 列構成：選択（チェックボックス）／節タイトル（編集可）／開始ページ（編集可）／出力デッキ名（編集可、自動補完あり）／最低カード枚数（編集可）／ソースファイル
- 検出精度・修正UIの使いやすさは同程度に重要

### 2. カード生成（AIプロバイダーのストラテジーパターン化）
- 利用するAIプロバイダー（Gemini／Claude／ChatGPT）とモデルバージョン（例：Gemini 2.5/3.5）の両方を切り替え可能にする
- Strategy Interface：`AiCardGeneratorRepository`（抽象基底クラス）
  - 共通メソッド：`generate_cards(section_text, prompt_context) -> CardContent`
- Concrete Strategy：`GeminiRepository` / `ClaudeRepository` / `ChatGptRepository`
  - プロバイダーの違いはクラスで分離、モデルバージョンの違いはコンストラクタ引数（`model_name`）で吸収
  - 各実装内部で構造化出力の強制方式（Geminiの`response_mime_type`、Claudeのtool use、GPTの`response_format`等）の違いを吸収し、外部には共通の`CardContent`オブジェクトを返す
- 設定（使用プロバイダー・モデル）は`.env`／`settings.json`で管理し、UseCases層はFactory経由でRepositoryインスタンスを取得する
- プロンプトは当面、全プロバイダーで同一の文面を使い回す（プロバイダー別チューニングのノウハウが現時点でないため）
  - `project_constitution.md`（AIへの役割・原則の指示）と`anki_generation.md`（カード生成の出力フォーマット指示）の2ファイル構成を踏襲する

### 3. カードテンプレート
- 既存の4段構成（論証／解説／要するに？／留意点）を維持する
- 色分けに意味はない（Ankiの標準ボタン配色に寄せているだけ）ため、変更不要
- 「要するに？」セクションは、監査論など実務未経験者がイメージしづらい分野の理解を助けるため、意図的にたとえ話を使う仕様とする（プロンプト側で明記）
- 各カードの文字数／行数制限は既存プロンプトの指示を踏襲する
- `PAGE_CODE`（PDF下部に記載された参照ページコード、例：③-8-1）は必須要件。AIがPDF実データから抽出する
  - 生成後のカード一覧側で、`PAGE_CODE`を軸にソート・検索できるようにする（「今この論点がテキストのどこにあるか」を頻繁に参照するため）

### 4. パッケージング
- genankiを用いた`.apkg`生成は既存踏襲

## 非機能要件・技術スタック

- フロントエンド：React (Vite) + TypeScript + Tailwind CSS
- バックエンド：FastAPI (Python)
  - PDF解析（PyMuPDF）・Gemini連携ロジックは既存の考え方を踏襲しつつ実装は作り直す
- 4層構造：
  ```
  routes/          # APIエンドポイント
  usecases/        # ビジネスロジック（構造スキャン、カード生成、パッケージング）
  repositories/
    ├─ ai/          # AiCardGeneratorRepository（Strategyパターン）
    ├─ pdf/          # PDF解析処理
    └─ anki/         # genanki呼び出しラッパー
  domain/           # エンティティ（Section, Card, Deck等）
  ```
- 構成管理：Docker Compose（frontend／backendコンテナ分離）
- スタイリングの細部（UI/UXの具体的な見た目）は初期実装をClaude Codeに任せ、実際に触った上で個別に修正依頼する方針とする。最初は動作優先

## APIキー・シークレット管理

- 各AIプロバイダー（Gemini／Claude／ChatGPT）のAPIキーは `.env` で管理し、`.gitignore`に含めてリポジトリにコミットしないこと
- キー名の例：`GEMINI_API_KEY`／`CLAUDE_API_KEY`／`OPENAI_API_KEY`（プロバイダーごとに1本、複数本のフォールバック対応は行わない。旧リポジトリの`GEMINI_API_KEY_1〜3`によるフォールバック機構は実際にはうまく機能した実績がなかったため、今回は廃止し、まずはシンプルに1プロバイダー1キーで構成する）
- Docker Compose側は旧リポジトリを踏襲し、`env_file`でbackendコンテナに読み込ませる形とする
- `.env.example`（キー名のみ、値は空）をリポジトリに含め、セットアップ時に何を用意すればよいか分かるようにすること

## 明示的にスコープ外とするもの

- 認証機能・ユーザー管理（Tailnet経由・単一ユーザー前提のため不要）
- 複数ユーザー対応
- 他アプリ（study-tracker-app等）との連携機能
- Anki（AnkiWeb／AnkiMobile）への自動インポート・自動同期機能
  - 検討の結果、AnkiWebには公開APIが存在せず、AnkiConnectはAnki Desktop限定のため、完全自動化は技術的に不可能と判明。手動でのSync操作を許容し、実装は見送る

## 実装順序の希望

1. ドメイン層の設計（Section, Card, Deck等のエンティティ定義）
2. repositories層の実装
   - `AiCardGeneratorRepository`の抽象化とGemini実装（他プロバイダーは後続で追加）
   - PDF解析ラッパー
   - genanki（Anki生成）ラッパー
3. usecases層の実装（構造スキャン処理、カード生成処理、パッケージング処理）
4. routes層の実装（APIエンドポイント）
5. フロントエンド：PDFアップロード〜構成確認・編集テーブルUI
6. フロントエンド：生成実行〜ダウンロードフロー

各ステップの実装後、何を実装したか・どのファイルにどんな責務を持たせたか・大きな設計判断をした場合はADRの要否も含めて簡潔に説明すること。
