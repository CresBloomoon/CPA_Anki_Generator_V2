# 要件定義：追加指示入力UI

## 背景

旧Streamlit版には、生成開始時に「追加指示」（例：「計算テキストで例題もカード化して」）を入力できるUIが存在していたが、V2への移植時にこの機能が抜け落ちていたことが判明した。

バックエンド側（`StartGenerationRequest`スキーマ、`GenerateCardsForSectionUsecase`、`prompt_builder.py`）は、`additional_prompt`を受け取りAI生成プロンプトに反映する経路が既に完成している。欠けているのはフロントエンド側の入力UIのみで、現状は`GenerationProgress.tsx`の`handleStart()`で`startGenerationJob()`の第2引数に空文字列がハードコードされている。

## 目的

ユーザー（まーくん）が、生成開始のたびに任意の追加指示を入力できるようにし、旧Streamlit版で使えていた「AIへの都度の細かい指示出し」を、V2でも再び行えるようにする。

## 要件

### 1. 入力単位

- ジョブ全体で1個。すべての選択セクションに対して共通の1つの追加指示を適用する。
- セクションごとに個別の指示を出す機能は、今回のスコープ外とする（バックエンドの設計（ジョブ全体で1つの`additional_prompt`を持つ構造）を変更しないことが前提のため）。

### 2. 配置

- セクションテーブルの下、生成開始ボタンの近くにテキストエリアを1個配置する。

### 3. 入力形式・制限

- 複数行入力可能なテキストエリアとする。
- 文字数の上限は設けない。

### 4. 保存・再利用

- 専用の保存機構（例：よく使う指示文をブラウザに保存しておく機能等）は今回作らない。
- 過去に使用した`additional_prompt`の再利用は、別途検討中の履歴機能（Step7）側でジョブ履歴の一部として表示することでカバーする方針とする。本UI自体には保存・呼び出し機能を持たせない。

### 5. 初期状態

- 未入力時は空欄とし、プレースホルダーで入力例を示す。
- プレースホルダーの文言例：「計算テキストで例題もカード化して」

## 主なユースケース（参考）

ユーザーが実際にどのような追加指示を入力しうるかの参考例。UI自体がこれらを個別に選択させる仕組み（プリセット等）を持つ必要はなく、あくまで自由記述のテキストエリアに対する入力例である。

- カード種別・粒度の指定（例：計算例題も個別にカード化してほしい）
- 特定分野への配慮強化（例：実務未経験者向けにたとえ話を多めに）
- 重複除外指示（例：他テキストで既にカード化済みの論点を除外）
- フォーマット微調整（例：`PAGE_CODE`の表記ゆれへの対応）
- 網羅性の強調（例：頻出論点のため論点漏れを避けたい）

## スコープ外

- セクションごとの個別追加指示
- 入力内容の専用保存機構（履歴機能側でカバーする方針のため）

## 現状把握（参考：既存の実装状況）

以下はいずれも実装済みで、変更不要であることを確認済み：

- `backend/app/routes/schemas/generation.py`：`StartGenerationRequest.additional_prompt: str = ""`
- `backend/app/routes/generation_routes.py`：`request.additional_prompt`を`StartGenerationJobUsecase.execute()`に渡す
- `backend/app/usecases/start_generation_job_usecase.py`：`additional_prompt`を`GenerationJob`に保持し、各セクションの生成呼び出しに渡す
- `backend/app/repositories/ai/dto.py`：`PromptContext.additional_prompt: str = ""`
- `backend/app/repositories/ai/prompt_builder.py`：`prompt_context.additional_prompt`が非空であれば、生成プロンプトに組み込む

フロントエンド側で欠けている部分：

- `frontend/src/components/GenerationProgress.tsx`：`handleStart()`内で`startGenerationJob(selectedRows.map(toSectionInput), '')`と第2引数が空文字列でハードコードされている
- 追加指示を入力するテキストエリア自体が、どのコンポーネントにも存在しない
