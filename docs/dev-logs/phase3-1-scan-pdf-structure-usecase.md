# Phase3-1: 構造スキャンUsecase（ルートパス反映）

## 実装したもの

- `backend/app/usecases/scan_pdf_structure_usecase.py`
  - `ScanPdfStructureUsecase.execute(pdf_files: list[PdfFileInput], root_path: str) ->
    ScanSectionsResult`：複数PDFをまとめてスキャンし、`root_path`を反映した
    `Section`（Phase1-1）のリストに変換する。
  - `SupportsScan`：`scan(pdf_bytes, source_file) -> ScanResult`を持つことだけを要求する
    構造的Protocol（詳細は「設計判断」参照）。
  - `PdfFileInput`：`pdf_bytes`＋`source_file`のペア。複数PDFをまとめて渡すための
    入力DTO。
  - `ScanSectionsResult`：`sections`（集約済み`Section`一覧）＋`warnings`（全ファイル分の
    警告を集約したもの）。
  - デッキパスの組み立て：各`RawSection.ancestors`（可変長）を`root_path`と`title`の間に
    順番に`DeckPath.child()`で挟み込む。階層が無い科目（`ancestors=()`）ではそのまま
    `root_path::title`になり、部→章のような多階層科目では
    `root_path::部::章::title`のように連鎖する。
- `backend/tests/usecases/test_scan_pdf_structure_usecase.py`：7ケース
  （フラット階層でのdeck_path組み立て、1階層／2階層のancestors挿入、source_file保持、
  複数PDFの集約、複数ファイル分のwarnings集約、page_rangeの透過）。

## 設計判断

`ScanPdfStructureUsecase`は具象クラス`PdfStructureRepository`を直接importせず、
`scan()`メソッドの型だけを要求する構造的Protocol（`SupportsScan`）に依存する設計とした。

理由：`PdfStructureRepository`（`pdf_structure_repository.py`）は`import fitz`を伴うため、
これを型ヒントとして直接importすると、Usecase層のモジュール自体がPyMuPDFに依存する
ことになり、Usecaseのテストでも（実際には使わないのに）PyMuPDFのスタブ化が必要に
なってしまう。直前に行った`RawSection`/`ScanResult`/`PdfParsingError`の`dto.py`への
分離（chore commit）は、まさにこの依存を断ち切るための準備だった。Protocolを使うことで、
テストでは`scan()`メソッドを持つ単純なフェイククラスを渡すだけで済み、Usecase・
テストのどちらもPyMuPDFへの依存がゼロになった。

## 実装中に発見したバグ・問題点

特になし。

## 動作確認

- このUsecaseはPyMuPDF・genanki・google-genaiのいずれにも依存しないため、サンドボックス
  内で直接実行し、テストファイルと同一のロジックで全ケースを事前に確認済み。
- 開発者側の実機で`docker compose run --rm backend sh -c "pip install -e .[dev] &&
  pytest"`を実行し、`107 passed in 7.43s`を確認済み（Phase2-6完了時点の100件＋今回の
  7件。実装時の報告では8件と誤って伝えていたが、実際のテストメソッド数は7件であり、
  手動検証スクリプトの`assert`呼び出し数と数え違えていたことが原因だった）。

## ADR

Protocolによる抽象化は小規模な設計判断であり、ADRを起票するほどの分岐ではないと
判断した。
