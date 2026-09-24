# トークン数表示機能

## 背景

生成中の進捗画面（`GenerationProgress`）と履歴タブの両方に、AI呼び出しの
トークン数を表示したいという要望を受けて着手した。

現状把握の結果、バックエンドはどのAIプロバイダー（Gemini/Claude/ChatGPT）
についても、APIレスポンスからトークン数を一切取得・保持していなかった
ことを確認した。`AiCardGeneratorRepository.generate_cards()`は`CardContent`
のみを返す共通契約になっており、これはストラテジーパターンの3実装すべて
が守っている契約のため、トークン数を扱うにはこの共通契約自体の変更が
必要だった。

Gemini SDK（`google-genai`）の`usage_metadata`の実際の属性名・型を、
`backend/tmp_samples/`に作成した確認スクリプトでDocker環境で検証した
（役目を終えたため実装完了後に削除済み）。

## 何を実装したか

- `backend/app/domain/generation_job.py`
  - `TokenUsage(input_tokens, output_tokens)`を新設（`total_tokens`
    プロパティ、`__add__`）。`SectionJob`が保持する必要があるため
    domain層に配置（後述）
  - `SectionJob`に`token_usage: TokenUsage`フィールドを追加
    （デフォルト`TokenUsage(0, 0)`）
  - `GenerationJob.total_token_usage() -> TokenUsage`を新設
    （`is_complete()`と同じ場所）。`collect_generated_cards()`とは異なり
    `status`によるフィルタリングを行わず、全`section_jobs`を合算する
- `backend/app/repositories/ai/dto.py`
  - `GenerationResult(card_content: CardContent, token_usage: TokenUsage)`
    を新設。`TokenUsage`はdomain層からインポートする
  - `AiCardGeneratorRepository.generate_cards()`の戻り値を`CardContent`
    から`GenerationResult`に変更（3プロバイダー共通の契約変更）
- `backend/app/repositories/ai/gemini_repository.py`
  - `response.usage_metadata`からトークン数を抽出。`input_tokens =
    prompt_token_count`、`output_tokens = total_token_count -
    prompt_token_count`（後述の発見を踏まえた式）
- `backend/app/repositories/ai/claude_repository.py`／
  `chatgpt_repository.py`
  - `GenerationResult(card_content, TokenUsage(0, 0))`を返す暫定スタブ。
    「未対応、実際に使うタイミングで対応する」旨をコメントで明記
- `backend/app/usecases/generate_cards_for_section_usecase.py`
  - `generate_cards()`の戻り値を`GenerationResult`として受け取り、
    `.card_content`/`.token_usage`に分解
  - `on_block_generated`コールバックの型を`Callable[[list[Card],
    TokenUsage], None]`に拡張し、ブロックごとの`token_usage`も渡す
- `backend/app/usecases/start_generation_job_usecase.py`
  - `run()`内の`persist_block`クロージャで、`section_job.cards.extend(...)`
    と同様に`section_job.token_usage = section_job.token_usage +
    token_usage`を追加
- `backend/app/repositories/jobs/generation_job_serializer.py`
  - `token_usage`の書き込み・読み込みを追加。読み込み側は`.get()`＋
    `TokenUsage(0, 0)`フォールバック（CLAUDE.mdの後方互換ルールに従い、
    本機能追加前の既存ジョブファイルでもKeyErrorにならないようにした）
- `backend/app/routes/schemas/generation.py`／`generation_routes.py`
  - `SectionJobStatusResponse.token_count`（合計のみ）、
    `GenerationJobSummaryResponse.total_token_count`（合計のみ）を追加
- フロントエンド
  - `frontend/src/api/types.ts`：上記2フィールドの型を追加
  - `frontend/src/components/GenerationProgress.tsx`：進捗テーブルに
    「トークン数」列をダウンロードボタン列の左に追加
  - `frontend/src/components/HistoryPanel.tsx`：展開後のセクション詳細
    テーブルに同様の列を追加、折りたたみ行のサマリーにジョブ全体の合計
    トークン数を追加
- テスト
  - `tests/domain/test_generation_job.py`：`TokenUsage`の算術・
    `SectionJob`のデフォルト値、`GenerationJob.total_token_usage()`が
    `FAILED`セクションも合算対象に含むことを確認する新規テスト
  - `tests/repositories/ai/test_gemini_repository.py`：実際に検証した
    Gemini呼び出しの値（後述）を再現し、`output_tokens`の算出式が正しい
    ことを確認する新規テスト
  - `tests/repositories/ai/test_claude_repository.py`／
    `test_chatgpt_repository.py`：`TokenUsage(0, 0)`スタブが返ることを
    確認する新規テスト、および既存の`result.items`アサーションを
    `result.card_content.items`に修正
  - `tests/usecases/test_generate_cards_for_section_usecase.py`／
    `test_start_generation_job_usecase.py`：`on_block_generated`が2引数
    になったことに伴う既存テストの修正、ブロック単位のトークン数が
    `SectionJob.token_usage`に正しく積み上がることを確認する新規テスト
  - `tests/repositories/jobs/test_generation_job_repository.py`：
    往復テストに`token_usage`を追加、`token_usage`キーが無い（本機能
    より前の）ファイルでも例外なく読み込めることを確認する新規テスト
  - `tests/routes/test_generation_routes.py`：進捗確認API・履歴一覧API
    のレスポンスに`token_count`/`total_token_count`が含まれることを確認

## 実装中に発見した問題点

Gemini SDKの`usage_metadata`を実際にDocker環境で確認したところ、
`gemini-2.5-flash`（思考機能を持つモデル）の呼び出しで以下の値が
返ってきた。

```
prompt_token_count = 16
candidates_token_count = 11
thoughts_token_count = 92
total_token_count = 119  (= 16 + 11 + 92)
```

当初の想定（「入力＝`prompt_token_count`、出力＝`candidates_token_count`」）
通りに実装すると、`thoughts_token_count`（実際に課金される思考過程の
トークン、この呼び出しでは全体の77%を占める）が丸ごと欠落し、合計が
27（実際の119の4分の1未満）になってしまうことが判明した。

対処として、`output_tokens`を`candidates_token_count`単体ではなく
`total_token_count - prompt_token_count`として定義し直した。この式なら
`thoughts_token_count`や将来Geminiが追加するかもしれない他の内訳
（`tool_use_prompt_token_count`等）が増減しても、`total_token_count`を
基準に引き算するだけなので取りこぼしが起きない。

## 大きな判断とその理由

- **`TokenUsage`をrepositories層（`dto.py`）ではなくdomain層
  （`generation_job.py`）に定義した**：`SectionJob`（domain層のクラス）
  が`token_usage`をフィールドとして直接保持する必要があるため、
  repositories層に置くとdomain→repositoriesという逆向きの依存が発生し、
  4層構造の一方向の依存原則が崩れる。既存の`CardContent`（`Card`が保持
  する必要があるため`domain/card.py`にあり、`dto.py`側がそこから
  インポートしている）と全く同じパターンを踏襲した。一方`GenerationResult`
  は、repositories層とusecases層の間でだけやり取りされる一時的な戻り値
  であり、domainのどのクラスもフィールドとして持つことはないため、
  `dto.py`に残置した
- **`output_tokens`を`total_token_count - prompt_token_count`として算出
  した**：上記「実装中に発見した問題点」の通り。`candidates_token_count`
  単体では思考トークンを取りこぼし、実際のコストを大幅に過小評価する
  ため
- **Claude/ChatGPTは`TokenUsage(0, 0)`の暫定スタブとした**：今回のスコープ
  はGeminiでの表示機能に限定し、Claude/ChatGPTは実際に選択されるタイミング
  で対応する（まーくんとの合意事項）。ただし、共通契約
  （`AiCardGeneratorRepository.generate_cards()`の戻り値）自体は3プロバイダー
  共通で変更する必要があったため、Claude/ChatGPT側も型としては
  `GenerationResult`を返すように最小限追従させた
- **`GenerationJob.total_token_usage()`は`status`によるフィルタリングを
  行わない**：`collect_generated_cards()`が`DONE`/`PARTIALLY_DONE`のみを
  対象とするのは「ダウンロード可能なカードか」という観点だが、トークンは
  `FAILED`で終わったセクションでも実際に課金されているため、正直な
  コスト集計には全件合算が正しいと判断した
- **APIレスポンスは合計のみを公開し、入力/出力の内訳は非公開とした**：
  表示粒度が合計のみと決まっているため。ドメイン層では`input_tokens`/
  `output_tokens`を分けて保持しており、将来内訳を表示する要望が出た場合も
  ドメイン層の変更なしにAPIレスポンスへ追加できる

## ADR

今回はADRを書くレベルの設計判断はなし。
