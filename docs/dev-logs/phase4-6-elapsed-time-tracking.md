# Phase4-6: セクション単位の経過時間トラッキング

## 背景

Phase5-17〜5-20（生成進捗の表形式化＋セクション単位ダウンロード）の一部として、
生成進捗テーブルに「経過時間」列を追加する設計が確定した。現状把握の結果、
`SectionJob`（domain）にも`SectionJobStatusResponse`（API）にも、開始・終了
時刻を記録するフィールドが存在しないことが判明したため、まず本Phaseで
バックエンド側のトラッキングを実装する。実際の表示（Phase5-26）は別Phase
として切り離す。

## 何を実装したか

- `backend/app/domain/generation_job.py`（修正）
  - `SectionJob`に`started_at: datetime | None = None`／
    `finished_at: datetime | None = None`を追加
  - `SectionJob.elapsed_seconds() -> int | None`を追加。`started_at`が
    `None`（＝`PENDING`）なら`None`を返し、`finished_at`があればその
    値、無ければ現在時刻との差分を秒数（整数）で返す
  - `mark_running()`で`started_at`を、`mark_done()`／`mark_failed()`
    （`PARTIALLY_DONE`／`FAILED`いずれの分岐でも共通）で`finished_at`
    を、それぞれ`datetime.now(timezone.utc)`で記録するよう変更
- `backend/app/routes/schemas/generation.py`（修正）
  - `SectionJobStatusResponse`に`elapsed_seconds: int | None`を追加
- `backend/app/routes/generation_routes.py`（修正）
  - `get_generation_job_status()`で`section_job.elapsed_seconds()`を
    呼び出し、レスポンスに含めるよう変更
- `frontend/src/api/types.ts`（修正）
  - `SectionJobStatusResponse`に`elapsed_seconds: number | null`を追加
    （型の同期のみ。表示ロジックへの反映はPhase5-26で行う）
- テスト
  - `tests/domain/test_generation_job.py`（修正）：`mark_running`／
    `mark_done`／`mark_failed`が`started_at`／`finished_at`を記録する
    ことを確認する既存テストへのアサーション追加、`elapsed_seconds()`
    の3パターン（`PENDING`で`None`、`RUNNING`中は現在時刻との差分、
    確定後は固定値）を確認する新規`TestElapsedSeconds`クラスを追加
  - `tests/routes/test_generation_routes.py`（修正）：既存の完了確認
    テストに、レスポンスの`elapsed_seconds`が`None`ではなく0以上の
    整数であることのアサーションを追加

## 実装中に発見したバグ・問題点

なし。

## 大きな判断とその理由

- **`elapsed_seconds()`をルート層ではなくdomain層（`SectionJob`自身の
  メソッド）に実装した**：このプロジェクトは既に`GenerationJob.
  is_complete()`／`collect_generated_cards()`のように、複数フィールド
  から導出される値をdomainオブジェクト自身のメソッドとして持たせる
  一貫した設計になっている。「経過時間」も同じ性質の導出値であり、
  同じ場所に置くことで一貫性を保った。ルート層に置くと、「実行中は
  現在時刻との差分、終了後は確定値」という分岐がHTTP層に漏れ出し、
  ルート層をHTTPのorchestrationとエラーマッピングに徹させるという
  既存の責務分離から外れてしまうため。
- **`RUNNING`中は`finished_at`が無ければ現在時刻との差分で計算する**：
  フロントエンドの2秒間隔のポーリングに乗せることで、専用のticking
  clockを追加せずとも、実行中の行の経過時間が見た目上進んでいるように
  表示できる（フロントエンドの表示ロジック自体はPhase5-26で実装）。
- **フロントエンドは型の同期のみ行い、表示ロジックには今回手を入れな
  かった**：`api/types.ts`のファイル冒頭コメントが「バックエンドの
  スキーマと型を一致させる」方針を明言しているため型定義自体は追加した
  が、実際の見た目（`mm:ss`形式への整形、「ー」表示の扱い等）は、
  Phase5-17〜5-20で合意した生成進捗テーブル（Phase5-26）の一部として
  作り込む想定のため、今回作っても書き直しになる可能性が高いと判断し、
  意図的に後続Phaseへ持ち越した。

## ADR

今回はADRを書くレベルの設計判断はなし。
