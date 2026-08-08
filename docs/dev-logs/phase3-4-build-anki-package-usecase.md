# Phase3-4: パッケージングUsecase

## 実装したもの

- `backend/app/usecases/build_anki_package_usecase.py`
  - `BuildAnkiPackageUsecase.execute(job: GenerationJob) -> AnkiPackageResult`：
    `job.collect_generated_cards()`（完了済みセクションのカードのみ、Phase1-4の
    状態機械が保証する）を`SupportsBuildPackage`経由で`.apkg`バイト列に変換する。
  - `SupportsBuildPackage`：`build_package(cards) -> bytes`を持つことだけを要求する
    構造的Protocol。Phase2-6の具象`AnkiPackageRepository`はgenankiに依存するため、
    Phase3-1／3-2と同じ理由でこのUsecase・そのテストをgenanki非依存に保つために
    採用した。
  - `AnkiPackageResult`：`apkg_bytes`と`is_complete`（`job.is_complete()`）のみを持つ。
    旧UXの「完了時はfinal、未完了時はpartialというファイル名・ラベルの切り替え」は
    HTTPレスポンスに関する関心事とみなし、このUsecaseでは`is_complete`のフラグを
    返すだけに留め、実際のファイル名・ラベル決定はPhase4-3のルート層に委ねる設計とした。
- テスト：`test_build_anki_package_usecase.py`（3ケース：全セクション完了時は
  `is_complete=True`、一部完了（1件成功・1件失敗・1件未着手）時は`is_complete=False`
  かつ完了済み分のカードのみが渡されること、1件も完了していない場合でも空リストで
  結果を返すこと）。

## 設計判断

`AnkiPackageResult`にファイル名やダウンロードラベルといったHTTP表現上の情報を含めず、
`is_complete`という真偽値のみを持たせた。これにより、このUsecaseは「ジョブの状態から
.apkgバイト列と完了フラグを作る」という純粋な変換処理に留まり、「完了/未完了で
ファイル名をどう変えるか」という表示上の判断はPhase4-3（ルート層）の責務として
明確に分離される。

## 実装中に発見したバグ・問題点

特になし。

## 動作確認

- このUsecaseはgenankiに依存しないため、サンドボックス内で直接実行し全7チェックを
  事前に確認済み。
- 開発者側の実機で`docker compose build backend`の後、`docker compose run --rm backend
  sh -c "pip install -e .[dev] && pytest"`を実行し、`140 passed`を確認済み
  （Phase3-3完了時点の137件＋今回の3件）。サンドボックスでの事前検証結果と一致。

これでStep3（UseCases層：構造スキャン／セクション単位カード生成／生成ジョブ
オーケストレーション／パッケージング）が全て完了した。次のStep4（Routes層）から、
これらのUsecaseを実際にHTTP API経由で呼び出す実装に入る。

## ADR

小規模な実装であり、ADRを起票するほどの分岐ではないと判断した。
