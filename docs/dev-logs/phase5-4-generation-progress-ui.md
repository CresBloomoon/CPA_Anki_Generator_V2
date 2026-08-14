# Phase5-4: 生成トリガー+進捗UI(ポーリング)

## 何を実装したか

- `frontend/src/api/types.ts`（修正）
  - `backend/app/routes/schemas/generation.py`に対応する型を追加：`SectionInput`／`StartGenerationRequest`／`StartGenerationJobResponse`／`SectionJobStatus`（union型）／`SectionJobStatusResponse`／`GenerationJobStatusResponse`。

- `frontend/src/api/client.ts`（修正）
  - `startGenerationJob(sections, additionalPrompt)`（`POST /generation-jobs`）、`getGenerationJobStatus(jobId)`（`GET /generation-jobs/{id}`）を追加。
  - `GenerationJobNotFoundError`（新規）：`GET /generation-jobs/{id}`が404を返した場合に投げる専用のエラー型。呼び出し側（`GenerationProgress`）が「ジョブが見つからない（再試行しても無意味）」と「その他の一時的な接続エラー（再試行の価値がある）」を区別できるようにするため。

- `frontend/src/components/GenerationProgress.tsx`（新規）
  - 選択済み行（`SectionRow.selected`でフィルタ）から生成ジョブを開始するボタン。開始後は`jobId`が確定するまで／ジョブ開始後は再度押せない（1セッション1回。やり直しはPhase5-6のリセットボタンに委ねる）。
  - `useEffect`（依存は`[jobId, onStatusChange]`のみ）内で`setInterval`によるポーリング（2秒間隔）。`is_complete`になった時点で自らインターバルを止める。アンマウント時は`cancelled`フラグと`clearInterval`の両方でガードし、アンマウント後の`setState`を防ぐ。
  - セクションごとの状態バッジ（PENDING/RUNNING/DONE/FAILED、色分け）、`card_count`・`error_message`の表示、全体進捗バー（DONE件数／全件数）。
  - ポーリング失敗時の挙動を、失敗の種類で分岐：
    - `GenerationJobNotFoundError`（404）：`JobStore`がインメモリのみのため、バックエンド再起動でジョブが消えると再試行しても無意味。即座にポーリングを停止し、確定的なエラーメッセージを表示する。
    - それ以外（ネットワークエラー等）：Tailscale経由のアクセスでは瞬断がありうるため、直近の表示は残したままポーリングを継続し、一時的な警告のみ表示する。
    - **連続失敗回数の上限（`MAX_CONSECUTIVE_POLL_FAILURES = 10`、約20秒相当）を追加**：バックエンドが完全に停止した状態が続くと、「接続エラーが発生しました。再試行中...」が無限に表示され続ける問題が実機確認で見つかったため。上限を超えたらポーリングを停止し、確定的なエラー表示に切り替える。成功時にカウントは0にリセットする（連続失敗のみをカウントし、累計失敗回数ではない）。

- `frontend/src/App.tsx`（修正）
  - `<GenerationProgress rows={rows} />`を配置。`onStatusChange`はPhase5-5（ダウンロードUI）まで消費者がいないため、今回は配線せず（オプショナルpropsとして用意だけしておく。Appに未使用のstateを持たせるとTypeScriptの`noUnusedLocals`に引っかかるため）。

- バックエンド側の副産物：進捗ログの追加（実機確認中に「生成に時間がかかっているが原因が分からない」という指摘を受けて追加。詳細は次項）
  - `backend/app/main.py`：`logging.basicConfig(level=logging.INFO)`を追加。uvicornは自身のロガーのみ設定し、アプリ側の`logging.getLogger(__name__)`は別途設定しないと黙って握りつぶされるため。
  - `backend/app/usecases/generate_cards_for_section_usecase.py`：ブロックごとに「[節タイトル] ブロック x/y 処理開始」「[節タイトル] ブロック x/y 完了、n件生成（n.n秒）」をINFOログ出力。
  - `backend/app/repositories/ai/gemini_repository.py`：Gemini API呼び出しの試行ごとに開始/成功/失敗（所要時間つき）をログ出力。失敗時はリトライ待機秒数も出力。

## 実装中に発見したバグ・問題点

- **生成に想定より時間がかかる事象**：まーくんの実機確認で、3セクション選択（うち第01章は58ページ）で生成を開始したところ、6分近く経過しても最初のセクションが完了しない事象が発生。推測で対応せず、以下を確認した：
  1. 進捗ログが一切無く、原因の切り分けができない状態だった（→ログを追加）。
  2. リトライ上限は`max_retries=3`（デフォルト）で無限ではないことを確認。ただしGemini API呼び出し自体にタイムアウト設定は無い。
  3. 第01章（58ページ）は`_SPLIT_THRESHOLD_PAGES=5`・`_MAX_PAGES_PER_BLOCK=4`のロジックにより15ブロックに分割される計算になり、これを直列に処理するため、1ブロックあたり20〜25秒程度でも合計5〜6分かかる計算上の説明がつくことを確認。

  最終的にまーくんの判断で、これは`gemini-2.5-pro`モデル自体の応答速度によるものであり（旧アプリでも同様の傾向があった）、Phase5-4の実装自体の問題ではないと結論づけられた。ただし調査の過程で追加した進捗ログは、今後同種の調査に役立つ副産物として残す。

- **バックエンド停止時、ポーリングが無限に「再試行中」を表示し続ける事象**：まーくんが実機確認中にバックエンドを完全に停止した状態でポーリングを継続させたところ発見。連続失敗回数の上限（10回、約20秒相当）を追加し、超過時にポーリングを停止して確定的なエラー表示に切り替えるよう修正した。

## 大きな判断とその理由

- **ポーリング失敗を「404（確定的）」と「その他（一時的）」で挙動を分けた**：Tailscale経由のアクセスという実環境の特性上、1回の失敗で即座にポーリングを止めると、一時的な瞬断でも進捗表示が完全に停止したように見えてしまう。一方でジョブが本当に消失した場合（バックエンド再起動）は再試行の意味が無いため、両者を区別した（まーくんとの合意事項）。
- **連続失敗上限の追加はPhase5-4のスコープに含め、別Phaseとして切り出さなかった**：発見された問題が、本Phaseで実装した`GenerationProgress`のポーリングロジックそのものへの直接的な拡張であり、新しいUI面や別コンポーネントを要しない小さな変更だったため（まーくんとの合意事項）。
- **`onStatusChange`はPhase5-4時点ではAppに配線しない**：Phase5-5（ダウンロードUI）まで実際の消費者がいないため、今configureすると未使用のstateがTypeScriptの`noUnusedLocals`エラーになる。propsとしては用意しておき、Phase5-5で配線する。

## ADR

今回はADRを書くレベルの設計判断はなし。
