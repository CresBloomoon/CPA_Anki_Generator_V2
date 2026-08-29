# Phase4-9: 重複課金リスク対応（D系統）

## 背景

APIコスト損失調査で洗い出したD系統（二重クリック・通信瞬断による自動再送・
別端末からの同一PDFの個別アップロードによる重複課金リスク）への対応。現状把握と
ユースケース整理を経て、冪等性キーにPDFバイト列のハッシュ値（SHA256）を含める
方式（③案）を採用した。ファイル名（`source_file`）のみをキーにする方式（②案）
では、別端末から同じPDFを異なるファイル名でアップロードされた場合に重複を
検知できないためである。

現状把握の過程で、`PdfStore.save()`が同一ファイル名に対して単純な辞書代入を
行っており、ファイル名が同じで中身が異なるPDFを2回アップロードすると、後からの
アップロードが前のバイト列を黙って上書きしてしまうバグも発見し、今回合わせて
修正した。

## 何を実装したか

- `backend/app/repositories/pdf/pdf_store.py`（修正）
  - `StoredPdf(pdf_bytes, content_hash)`という値オブジェクトを新設し、
    `_pdfs`の値をこの型に変更。既存の`source_file`キーはそのまま維持した。
  - `PdfContentMismatchError`を新設。`save()`は、既存エントリと異なる
    ハッシュ値の内容が同じファイル名で保存されようとした場合にこの例外を
    送出する。ハッシュ値が一致する（＝実質的に同一内容の）再保存は今まで
    通り成功する。
  - `get_content_hash(source_file) -> str`を新規追加。
  - `get()`の戻り値型（`bytes`）は変更していない。
- `backend/app/routes/pdf_routes.py`（修正）
  - `upload_pdf()`で`PdfContentMismatchError`を捕捉し、409を返す。
- `backend/app/domain/generation_job.py`（修正）
  - `GenerationJob`に`idempotency_key: str = ""`を追加。
- `backend/app/repositories/jobs/job_store.py`（修正）
  - `find_by_idempotency_key(key) -> GenerationJob | None`を追加（線形走査）。
    完了済みかどうかの判定はここでは行わない素朴な検索。
- `backend/app/usecases/start_generation_job_usecase.py`（修正）
  - `DuplicateGenerationJobError`を新設。
  - `_build_idempotency_key()`を追加：各選択セクションの
    `(content_hash, start_page, end_page, deck_path, title)`をソートし、
    `additional_prompt`と合わせてSHA256ハッシュ化する。
  - `execute()`を変更：冪等性キーを計算し、`job_store.find_by_idempotency_key()`
    で一致するジョブが見つかり、かつそのジョブが未完了であれば
    `DuplicateGenerationJobError`を送出する。それ以外は従来通りジョブを
    構築・保存する（`idempotency_key`も一緒に保存）。
- `backend/app/routes/generation_routes.py`（修正）
  - `start_generation_job()`で`DuplicateGenerationJobError`を409、
    `PdfNotFoundError`を404にマッピング（後者は実装中に新たに発見した
    副作用への対応、詳細は次項）。
- テスト：`test_pdf_store.py`／`test_pdf_routes.py`／`test_generation_job.py`／
  `test_job_store.py`／`test_start_generation_job_usecase.py`／
  `test_generation_routes.py`にそれぞれ対応するテストを追加・修正。

## 実装中に発見したバグ・問題点

`_build_idempotency_key()`が各セクションについて
`pdf_store.get_content_hash(section.source_file)`を呼ぶ必要があるため、
この計算が`StartGenerationJobUsecase.execute()`内で**同期的に**実行される
ようになった。これにより、一度もアップロードされていない`source_file`を
参照するセクションを含むリクエストが来た場合、従来は「ジョブは作られ、
バックグラウンドスレッド内でそのセクションだけ`FAILED`になる」という挙動
だったのが、**`execute()`自体が`PdfNotFoundError`を送出し、ジョブが一切
作られなくなる**という挙動に変わった。この経路はこれまでどちらのテストにも
存在せず明示的な契約が無かったため、まーくんに報告の上、`/scan`エンドポイント
の既存パターン（`PdfNotFoundError` → 404）に倣い、`generation_routes.py`にも
同じマッピングを追加する形で対応した。

また、`test_generation_routes.py`の`_FakeAiRepository.__init__`に
`release_event: threading.Event | None = None`引数を追加したところ、この
ファイル内の無関係な既存テスト6件が
`FastAPIError: Invalid args for response field!`で失敗する事象が、まーくんの
Docker環境でのpytest実行により発見された。原因は、`client`フィクスチャが
`app.dependency_overrides[get_ai_card_generator_repository] = _FakeAiRepository`
と**クラスそのもの**をオーバーライドに渡していたこと。FastAPIはオーバーライド
された呼び出し可能オブジェクトをリクエストのたびにシグネチャ解析して依存関係
グラフを再構築するため、`__init__`に増えた`release_event`引数を（`Depends(...)`
でマークされていない）クエリパラメータ相当とみなしてPydanticフィールド化しよう
とし、`threading.Event`がPydanticの検証可能な型ではないため失敗していた。
`get_pdf_store`／`get_job_store`と同じ「インスタンスを返すラムダ」形式
（`lambda: _FakeAiRepository()`）に統一することで解消した。

## 大きな判断とその理由

- **`PdfStore`のキーは`source_file`のまま維持し、ハッシュ値は`StoredPdf`
  として併用した**：`source_file`はアプリ全体（`Section`・`SectionInput`・
  フロントエンドのテーブル列・`StartGenerationJobUsecase.run()`）で一貫して
  PDFを参照する識別子として使われている。ハッシュ値をキーそのものに置き換える
  と、これら全ての参照箇所を書き換える必要が生じ、影響範囲が今回の目的に対して
  過大になるため、既存の識別子はそのまま残し、ハッシュ値は付随情報として
  追加する形にした。
- **上書きバグはエラーとして拒否する形にし、自動リネームでの保持は行わなかった**：
  自動リネーム案は、リネーム後の識別子をフロントエンドにどう伝えるかという
  新たな問題を生み、かつユーザーの意図（間違えて選び直しただけか、本当に別
  ファイルとして扱いたいのか）をアプリ側が推測することになる。CLAUDE.mdの
  「推測によるデバッグを行わない」という方針とも合わないため、明示的な
  エラーとして即座に知らせ、判断をユーザー自身に委ねる形にした。
- **重複判定のポリシーは`JobStore`ではなく`StartGenerationJobUsecase`に
  集約した**：`find_by_idempotency_key()`は「完了済みかどうか」を判定しない
  素朴な検索のみを行う。「何が重複とみなされるか」という業務ルールは、
  B-2の連続失敗閾値と同様usecases層に置くのが、この既存の設計と一貫すると
  判断したため。
- **完了済みジョブは重複判定の対象外とした**：まーくんと決定済みのエラー
  文言が「同じ内容のジョブが既に実行中である」となっている通り、意図は
  「今動いている重複を防ぐ」ことである。過去に完了・ダウンロード済みの
  ジョブと同じ内容を意図的にもう一度生成したい場合（カードの作り直し等）
  まで永久にブロックするのは過剰だと判断した。
- **冪等性キーに`title`を含めた**：ページ範囲・デッキ名が同じでもタイトルを
  変えれば生成されるカードの見出しが変わるため、これも「内容が同一かどうか」
  の判定に含めるべきと判断した。

## ADR

今回はADRを書くレベルの設計判断はなし。
