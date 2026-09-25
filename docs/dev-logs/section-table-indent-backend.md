# スキャン結果テーブルの字下げ（バックエンド）

## 背景

スキャン結果テーブル（`SectionTable.tsx`）で、章・節などの階層構造を字下げ
（インデント）で視覚的に区別したいという要望を受けて着手した。

現状把握の結果、PDFのTOC階層情報のうち、`RawSection.ancestors`は
`PdfStructureRepository._build_sections_from_toc()`が各深さで直近に見た
タイトルを追跡することで算出している一方、`RawSection.level`は
`doc.get_toc()`が返す値をそのまま使っていることを確認した。この`level`は
`ScanPdfStructureUsecase._build_deck_path()`が`ancestors`を単一の
`deck_path`文字列へ畳み込んだ時点で捨てられており、`/scan`のAPIレスポンス
にも`SectionTable.tsx`側のドメインにも階層の深さ情報が一切残っていない
ことを確認した。

ADR 0001（TOC-only検出方針）が示す通り、階層の深さは科目によって異なる
（企業法／監査論：章→節の2階層、管理会計論：フラットな1階層、財務会計論：
部→章の2階層）ため、「章／節」のような固定ラベルに基づく字下げ実装は
一部の科目で成立しない。このため、フロントエンドでタイトル文字列を
パターンマッチして階層を推測するアプローチは採らず、スキャン時に確定する
`level: int`（深さ）をそのままAPI経由で公開する方針とした。

まーくんとの相談の結果、以下の2点を設計方針として決定した。

1. 字下げの深さは、スキャン時にPDFのTOCから得た`level`で固定する。
   出力デッキ名（`deck_path`）やタイトルを編集しても、字下げは変わらない
   （インデントは「編集後のdeck_pathから都度導出」ではなく「スキャン時点の
   スナップショット」）
2. 「行を追加」で手動追加した行は、字下げなし（一番左）のまま表示する

この2点を踏まえ、本Phase（`section-table-indent-backend`）ではバックエンド側
（`level`をAPIレスポンスとして公開するところまで）を実装した。字下げの
描画自体は次の`section-table-indent-frontend`Phaseで行う。

## 何を実装したか

- `backend/app/usecases/scan_pdf_structure_usecase.py`
  - `ScannedSection(section: Section, level: int)`を新設。`Section`と
    スキャン時点の深さ`level`をペアで運ぶ
  - `ScanSectionsResult.sections`の型を`tuple[Section, ...]`から
    `tuple[ScannedSection, ...]`に変更
  - `execute()`内で、`RawSection.level`を`ScannedSection.level`にそのまま
    詰めるよう変更（`_build_deck_path()`自体は変更なし）
- `backend/app/routes/pdf_routes.py`
  - `scan_pdfs()`のレスポンス組み立てを`scanned.section.xxx`経由に変更し、
    `SectionScanResult`に`level=scanned.level`を追加
- `backend/app/routes/schemas/pdf.py`
  - `SectionScanResult`に`level: int`フィールドを追加（フロントエンド表示
    専用で、カード生成には使わない旨をコメントで明記）
- テスト
  - `tests/usecases/test_scan_pdf_structure_usecase.py`：既存8件を
    `.sections[0].xxx` → `.sections[0].section.xxx`に機械的に修正。
    `TestScannedSectionLevel`クラスを新設し、フラット1階層・部→章→節の
    3階層それぞれで`level`が正しく詰められることを確認する2件を追加
  - `tests/routes/test_pdf_routes.py`：既存の
    `test_scan_returns_sections_with_hierarchy_reflected_in_deck_path`に、
    章（level=1）・節（level=2）の`level`アサーションを追加
  - `tests/repositories/pdf/test_pdf_structure_repository.py`：後述

## 実装中に発見した問題点

### テスト名が実際の検証内容を正確に表していなかった

`TestScannedSectionLevel`に最初に書いた
`test_level_matches_the_number_of_ancestor_levels`は、フェイクリポジトリに
`level`と`ancestors`の両方を独立した値として渡しているだけで、
`ScanPdfStructureUsecase.execute()`は`level`を`ancestors`の段数から算出する
処理を一切行っていない（`RawSection.level`を`ScannedSection.level`へ
そのままパススルーしているだけ）。つまりこのテストが実際に確認していたのは
「usecase層でのパススルー」のみであり、テスト名が示唆する「levelが
ancestorsの段数と一致することの検証」にはなっていなかった。

まーくんからの指摘（Socratic形式の質問）を受けて調査し、以下を確認した。

- `level`はどこでも算出しておらず、`PdfStructureRepository
  ._build_sections_from_toc()`がPyMuPDFの`doc.get_toc()`が返す値
  （`(level, title, page)`のフラットなリスト）の`level`をそのまま使っている
- `ancestors`はこれとは別に、「各深さで直近に見たタイトル」を
  `ancestors_by_level: dict[int, str]`で追跡することで独立に構築している
- `level == len(ancestors) + 1`が成り立つのは、「TOCの階層番号が1から
  欠番なく振られている」という**入力データ側の性質**であり、コードが
  保証しているものではない（TOCの階層番号が飛んでいるような不整合な
  入力があれば、この対応関係は崩れうる）

テスト名を実際の検証内容に合わせて
`test_level_is_forwarded_unchanged_for_each_section`にリネームした
（テスト本体は無変更）。

### 既存テストに「levelの多階層での正しさ」を検証する箇所が存在しなかった

上記の調査の過程で、`level`と`ancestors`の対応関係を実際に検証できる唯一の
場所である`tests/repositories/pdf/test_pdf_structure_repository.py`の
`test_part_chapter_hierarchy_disambiguates_duplicate_titles`（部→章の
2階層、財務会計論を模したフィクスチャ）が、`ancestors`は丁寧に検証している
一方で`level`には一切アサーションがないという、本Phase以前から存在していた
テストカバレッジの穴を発見した。

本Phaseで`level`が`/scan`のAPIレスポンスとして外部公開されることになった
ため、その出どころである`PdfStructureRepository`側でも`level`の正しさを
保証しておく必要があると判断し、既存のアサーション（`ancestors`等）は
変更せず、以下の1行を追加した。

```python
assert [s.level for s in sections] == [1, 1, 2, 2, 1, 2]
```

## 大きな判断とその理由

- **`level`を`Section`ドメインに持たせず、usecase層に新設した
  `ScannedSection`で運ぶ**：`Section`は、スキャン結果からだけでなく
  `SectionInput`（生成リクエストの入力）からも生成される共有ドメイン型
  （`generation_routes.py`）であり、生成リクエスト側には「深さ」という
  概念自体が存在しない。ここに`level`を追加すると、スキャン時の表示専用
  の関心事が生成フロー全体で共有されるドメイン型に漏れ出してしまう。
  そのため、`Section`本体はそのままに、`ScannedSection(section, level)`
  というusecase層限定のペア型で深さ情報を運ぶことにした
- **`ScannedSection`を「2つの並行した配列」ではなく「ペアの配列」にした**：
  `sections: tuple[Section, ...]`と`levels: tuple[int, ...]`を別々に持つ
  実装も検討したが、将来フィルタリングや並び替えを追加した際に両者が
  黙って食い違うリスクがある。ペアにしておけば、そのリスク自体が構造的に
  排除できる。このトレードオフとして、既存テスト8件を`.sections[0].xxx`
  → `.sections[0].section.xxx`に機械的に修正するコストが発生したが、
  受け入れた
- **テスト名は「実際に確認している内容」に合わせてリネームした**：
  「levelがancestorsの段数と一致することを確認するテスト」という体裁の
  テストが実際には「usecase層でのパススルー」しか確認していないと、
  将来levelの算出ロジック自体にバグが入っても発見できない安心感を
  与えてしまう。テスト名と検証内容を一致させることを優先した
- **`test_part_chapter_hierarchy_disambiguates_duplicate_titles`への
  level追加は、既存アサーションを変更せず1行追加のみにとどめた**：
  今回の目的はカバレッジの穴を埋めることであり、既存の`ancestors`検証の
  意図・粒度を変える必要はないため

## 次の`section-table-indent-frontend`Phaseへの引き継ぎ事項

- `SectionRow`（`SectionTable.tsx`）に`level: number | null`を追加し、
  `/scan`レスポンスの`level`をそのままコピーする
- 「行を追加」（`addRow()`）で手動追加した行は`level: null`とし、
  字下げなし（一番左）で表示する
- インデント量の算出は`row.level ? row.level - 1 : 0`のような曖昧な
  三項演算子ではなく、`row.level !== null`のように「nullかどうか」を
  明示的に判定する書き方にする（null＝手動追加行という意図がコード上で
  読み取れるようにするため）
- 字下げを文字（テキスト）に付けるか、入力欄ごとずらすかは、実装後に
  実機で見た目を確認してから決める

## ADR

今回はADRを書くレベルの設計判断はなし（階層の深さをintで扱う方針自体は
既存のADR 0001の射程内であり、新規のADRは不要と判断した）。
