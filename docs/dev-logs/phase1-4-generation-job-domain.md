# Phase1-4: ドメイン層 GenerationJob

## 実装したもの

- `backend/app/domain/generation_job.py`
  - `SectionJobStatus`：`PENDING`/`RUNNING`/`DONE`/`FAILED`の列挙。
  - `SectionJob`：`section`（Phase1-1の`Section`）／`status`／`cards`（Phase1-2の`Card`一覧）／
    `error_message`を持つ可変の子エンティティ。`status`はPhase1-3の`Deck`と同じ方針で、
    外部から直接書き換えず`GenerationJob`のメソッド経由でのみ変更する想定。
  - `GenerationJob`：`job_id` + `section_jobs`を持つ可変アグリゲートルート。
    - `mark_running(index)`／`mark_done(index, cards)`／`mark_failed(index, error_message)`：
      `PENDING → RUNNING → (DONE | FAILED)`という一方向の状態遷移のみを許可し、想定外の
      遷移（例：`DONE`のセクションへの再度の`mark_running`）は`ValueError`を送出する。
    - `is_complete()`：全セクションが`DONE`のときのみ`True`。
    - `collect_generated_cards()`：`DONE`のセクションのカードのみを集約する。
- `backend/tests/domain/test_generation_job.py`：12ケース。状態遷移の正常系・異常系、
  `is_complete()`の真偽、および旧`main.py`の「1セクション失敗で残りは中断するが完了済みは
  保持する」というUX契約を再現するシナリオ（1番目`DONE`／2番目`FAILED`／3番目`PENDING`で
  停止し、`collect_generated_cards()`が1番目の分だけ返す）を検証。

## 設計判断

- 状態遷移に前提条件チェックを設けた（`mark_running`は`PENDING`からのみ、`mark_done`/
  `mark_failed`は`RUNNING`からのみ許可）。単なるフィールドの入れ物ではなく「状態機械として
  表現する」という計画上の意図を、実際に不正な遷移を拒否するコードとして裏付けるため。
  これにより、Usecase層（Phase3-3）が誤って完了済み・失敗済みのセクションを再実行しようと
  した場合に、サイレントな不整合ではなく明示的なエラーとして検知できる。
- `is_complete()`は「全セクションが`DONE`」を意味する（旧`main.py`の
  `generated_count >= total_selected`相当）。一部`FAILED`のまま停止したジョブは、
  ユーザーが再実行しない限り「完了」とはみなさない。

## 動作確認

- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend sh -c
  "pip install -e .[dev] && pytest"`を実行し、`37 passed in 0.71s`を確認済み
  （Phase1-1〜1-3の25件＋今回の12件）。

## 発見した問題点

特になし。

## ADR

状態遷移に前提条件チェックを設けた判断は小規模な設計判断であり、ADRを起票するほどの
分岐ではないと判断した。これでStep1（ドメイン層：Section／Card／Deck／GenerationJob）が
完了。次のStep2（Repositories層）から、これらのドメインオブジェクトを実際に構築・利用する
実装に入る。
