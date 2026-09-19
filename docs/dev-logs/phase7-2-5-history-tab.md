# Phase7-2-5: フロントエンド 履歴タブ本体

## 背景

Phase7-2-1〜7-2-4で、ジョブの永続化・再起動後の読み込み・履歴一覧取得API
（`GET /generation-jobs`）までバックエンド側が完成した。本Phaseはこれを
フロントエンドの履歴タブとして実際に使える形にする。

現状把握の結果、既存の`SettingsPanel`（独立した子コンポーネントに完全に
委譲するパターン）・`SectionDownloadButton`（進行中/履歴どちらのジョブにも
無調整で使える汎用実装）・`getGenerationJobStatus()`（既存のセクション詳細
取得API、アコーディオン展開時にそのまま再利用可能）を踏襲すれば、新規の
バックエンドAPIを増やさずに実装できることを確認済みだった。

## 何を実装したか

- `frontend/src/utils/sectionJobStatus.ts`（新規）
  - `SECTION_JOB_STATUS_LABELS`／`SECTION_JOB_STATUS_BADGE_CLASSES`を
    `GenerationProgress.tsx`から切り出し、`HistoryPanel`とも共有できるように
    した（同じステータス表現をコンポーネント間で重複させないため）
- `frontend/src/components/GenerationProgress.tsx`（修正）
  - 上記の切り出しに伴うimport差し替えのみ。挙動・見た目は無変更
- `frontend/src/api/types.ts`（修正）
  - `GenerationJobSummaryResponse`／`GenerationJobListResponse`を追加
    （バックエンドの同名Pydanticスキーマに対応）
- `frontend/src/api/client.ts`（修正）
  - `listGenerationJobs()`（`GET /generation-jobs`）を追加
- `frontend/src/components/HistoryPanel.tsx`（新規）
  - マウント時に`listGenerationJobs()`を取得。`isLoading`／`error`は
    `SettingsPanel`と同じくローカルstateで持つ
  - `expandedJobId: string | null`による単一展開アコーディオン
  - セクション詳細（`getGenerationJobStatus(jobId)`）はjob_idごとに
    `jobDetails`へキャッシュし、初回展開時のみ取得。取得成功時のみ
    キャッシュし、失敗時はキャッシュせず次回展開時に再取得を試みる
    （一時的なエラーで恒久的に固まらないようにするため）
  - 詳細取得のエラーは`detailErrors: Record<jobId, string>`でjob_idごとに
    個別管理し、失敗したジョブの行だけにエラー表示が出るようにした
  - 一覧の見出しは`root_path || ジョブ{job_id先頭8文字}`。`root_path`は
    フロントがまだ送信していない（Phase7-2-6未着手）ため現時点では常に
    空文字になり、フォールバック表示が必須だった
  - 展開後はセクションごとの状態バッジ・タイトル・既存の
    `SectionDownloadButton`（無調整で再利用、`onDownloaded`は空関数）を
    表形式で表示
- `frontend/src/App.tsx`（修正）
  - `history`タブのプレースホルダーを`<HistoryPanel />`に置き換え

## 実装中に発見したバグ・問題点

まーくんの実機確認で、履歴タブを開くと`GET /generation-jobs`が
500エラーになる不具合が見つかった。

調査の結果、`backend/data/generation_jobs/`配下に**Phase7-2-4より前**
（`created_at`フィールド追加前）に永続化されたジョブファイルが1件残って
おり、`generation_job_serializer.py`の`job_from_dict()`が
`data["created_at"]`という直接キーアクセスをしていたため、このキーを
持たない古いファイルを読み込んだ際に`KeyError`が発生していた。
`GenerationJobRepository.list_all()`はディレクトリ内の全ファイルを
読み込むため、この1件が混ざっているだけで一覧取得API全体が落ちていた。

実データを直接確認したところ、該当ファイルは3セクション・カード69枚分の
実際に完了した生成結果だったが、まーくんの判断で削除して問題ないことを
確認した上で削除した（コンテナがroot権限で作成したファイルだったため、
Claudeの実行権限では削除できず、まーくんに削除を依頼した）。

恒久対策として、`job_from_dict()`を`data.get("created_at")`＋フォール
バック値（`_UNKNOWN_CREATED_AT`、`datetime.min`のtz-aware版）を使う形に
修正した。この値は`ListGenerationJobsUsecase`の新しい順ソートで自動的に
最後尾に回るため、「作成時刻不明」という扱いとして自然に振る舞う。回帰
テスト（`TestBackwardCompatibility`）を`test_generation_job_repository.py`
に追加し、`created_at`キーの無いファイルが例外無く読み込めること、他の
正常なジョブと混在していても`list_all()`が全件返すことを確認した。

再発防止のため、CLAUDE.mdに「永続化データへのフィールド追加時の後方互換
ルール」を追記した（今後スキーマにフィールドを追加する際は、既存の古い
ファイルにそのフィールドが無くても壊れない実装を徹底する）。

## 大きな判断とその理由

- **`GenerationJob.created_at`のドメイン側の型は`datetime`のまま変更
  しなかった**：`created_at`が無い古いファイルへの対応は、あくまで
  デシリアライズ境界（`generation_job_serializer.py`）だけの問題であり、
  ドメイン層やその外側（`ListGenerationJobsUsecase`のソートキー、
  `GenerationJobSummaryResponse`等）にOptional対応を波及させるのは
  過剰だと判断した
- **フォールバック値を`datetime.min`にした**：新しい順ソートで確実に
  最後尾（＝最も古い扱い）に回ることを保証するため。まーくんの提案
  （「Noneを許容してソート時は末尾に回す」）と同じ効果を、ドメイン層に
  手を入れずに実現した
- **`_UNKNOWN_CREATED_AT`が実際に一覧表示された場合のフロント対応は
  見送った**：削除対象の1件以外にこのフォールバックが発動するケースが
  現状存在せず、発動しても表示上の見た目の問題（「0001/1/1」と表示される
  等）に留まりクラッシュはしないため。将来実際に発生した場合に検討する旨を
  コード内にコメントで残した
- **`root_path`・`idempotency_key`・`additional_prompt`等、他の永続化
  フィールドは`.get()`化しなかった**：これらは永続化の仕組み自体
  （Phase7-2-1）が導入された最初の時点から存在しており、`created_at`の
  ような「後から追加されて過去のファイルに無い」という状況が起こり得ない
  ため。起こり得ないケースへの予防的な変更は行わない方針とした
- **`SECTION_JOB_STATUS_LABELS`/`SECTION_JOB_STATUS_BADGE_CLASSES`を
  共有ユーティリティに切り出した**：`GenerationProgress`と`HistoryPanel`
  の両方が同じステータス表現を必要としたため、重複させず1箇所に集約した

## ADR

今回はADRを書くレベルの設計判断はなし。
