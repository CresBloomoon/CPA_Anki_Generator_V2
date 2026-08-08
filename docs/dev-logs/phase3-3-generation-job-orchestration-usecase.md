# Phase3-3: 生成ジョブオーケストレーションUsecase（非同期・インメモリ・ポーリング）

## 実装したもの

- `backend/app/repositories/pdf/pdf_store.py`：`PdfStore`。アップロード済みPDFバイト列を
  `source_file`（ファイル名）をキーにインメモリで保持する（旧`st.session_state.pdf_info`
  相当）。永続化なし・`threading.Lock`で排他制御。見つからない場合は`PdfNotFoundError`。
- `backend/app/repositories/jobs/job_store.py`：`JobStore`。`GenerationJob`を`job_id`を
  キーにインメモリで保持する。永続化なし・`threading.Lock`で排他制御。見つからない場合は
  `JobNotFoundError`。
- `backend/app/usecases/start_generation_job_usecase.py`：`StartGenerationJobUsecase`
  - `execute(sections) -> str`：選択済み`Section`一覧から`GenerationJob`を作成し
    `JobStore`に登録した上で、`threading.Thread`（daemon）でバックグラウンド実行を
    開始し、即座に`job_id`を返す。
  - `run(job)`：セクションを順に`mark_running`→`GenerateCardsForSectionUsecase.execute`
    →`mark_done`（成功時）／`mark_failed`（失敗時、以降のセクションは処理せず中断）。
- `backend/app/usecases/get_generation_job_status_usecase.py`：
  `GetGenerationJobStatusUsecase.execute(job_id) -> GenerationJob`。クライアントは
  これをポーリングして進捗を確認する想定。
- テスト：`test_pdf_store.py`（4ケース）、`test_job_store.py`（4ケース）、
  `test_start_generation_job_usecase.py`（3ケース、うち1つは実際の`threading.Thread`を
  使った`execute()`のポーリング統合テスト）、`test_get_generation_job_status_usecase.py`
  （2ケース）。

## 設計判断：計画からの変更点（asyncio→threading）

当初の計画では「`asyncio.Lock`」「FastAPIの`BackgroundTasks`」を想定していたが、
実装前にユーザーと協議の上、以下の理由で`threading`ベースに変更した。

Phase2-3で実装済みの`GeminiRepository.generate_cards`は完全に同期的
（`time.sleep()`によるブロッキングリトライ）である。FastAPIの`BackgroundTasks`に
同期関数を渡すと、Starlette内部で別スレッド（スレッドプール）上で実行される。
つまりジョブ実行スレッドとステータス確認（GET）を処理するスレッドは別々のOSスレッドに
なり、`asyncio.Lock`はスレッドをまたぐ排他制御には効かない（同一イベントループ上の
コルーチン間でしか機能しないため）。

そのため：
- `JobStore`／`PdfStore`の排他制御は`threading.Lock`を採用した。
- バックグラウンド実行はFastAPIの`BackgroundTasks`に頼らず、
  `StartGenerationJobUsecase`自身が`threading.Thread`を起動する設計にした。これにより
  Usecase層がFastAPI固有の仕組みに一切依存しなくなり、Phase4-3のルート層は
  `usecase.execute(...)`を呼んで返ってきた`job_id`をレスポンスするだけで済む。

## テストにおける工夫

`execute()`はバックグラウンドスレッドを起動して即座に戻ってくるため、テストから
その完了を待ち合わせる標準的なハンドル（スレッドオブジェクト）を返さない設計にした。
そこで`run(job)`を公開メソッドとして切り出し、詳細な状態遷移（1セクション失敗時に
残りが`PENDING`のまま停止する等）のテストは`run()`を同期的に直接呼び出す形で検証した。
`execute()`自体のテストは、フェイクの依存（即座に応答する）を使い、`job.is_complete()`
を短いタイムアウト付きでポーリングする形にすることで、実スレッドを使った統合テストを
フレーキーにならない範囲で実現した。

## 実装中に発見したバグ・問題点

特になし。

## 動作確認

- このPhaseはPyMuPDF・genanki・google-genaiのいずれにも依存しないため、サンドボックス
  内で`threading`の実動作も含めて全22チェック（Phase3-3の受け入れ基準：3セクション中
  2番目が失敗し、1番目`DONE`・2番目`FAILED`・3番目`PENDING`で停止、
  `collect_generated_cards()`が1番目の分だけ返すことを含む）を直接確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`137 passed`を確認済み
  （Phase3-2完了時点の124件＋今回の13件）。サンドボックスでの事前検証結果と一致。

## ADR

`asyncio`から`threading`への変更は、Phase2-3の実装済みコード（完全同期的な
`GeminiRepository`）という既存事実から論理的に導かれる判断であり、新たな設計判断という
よりは計画と実装済みコードの整合性を取ったものと位置づけ、ADRを起票するほどの分岐では
ないと判断した。
