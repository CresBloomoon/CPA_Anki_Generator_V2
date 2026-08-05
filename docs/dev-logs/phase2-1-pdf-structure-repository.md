# Phase2-1: PDF構造解析リポジトリ

## 何を実装したか

- `backend/app/repositories/pdf/pdf_structure_repository.py`（全面書き換え。詳細な経緯・
  設計判断は[ADR 0001](../adr/0001-pdf-structure-detection-toc-only.md)を参照）
  - `PdfStructureRepository.scan(pdf_bytes, source_file) -> ScanResult`：`doc.get_toc()`の
    フラットな`(level, title, page)`列を1回走査し、各レベルで直近に見たタイトルを保持する
    辞書から祖先タイトル列（`ancestors`）を組み立てる。階層数・単位名（章／節／部等）を
    コードで一切仮定しない。
  - `PdfStructureRepository.extract_text_from_range(...)`：ページ範囲のテキストを
    `"--- ページ N ---"`マーカー付きで抽出（Phase3-2のカード生成Usecaseが利用する想定）。
  - `RawSection`（`title`/`ancestors`/`level`/`page_range`/`source_file`）、`ScanResult`
    （`sections`/`warnings`）、`PdfParsingError`。
  - `_normalize_title`：先頭が`第<算用数字><部/編/章/節/項/款>`の形にマッチする場合のみ
    数字をゼロ埋めする軽量な正規化。マッチしないタイトル（目次／はじめに／序章／補章／
    漢数字タイトル等）はそのまま素通しする。
- `backend/app/domain/section.py`：`Section.chapter_title`／`Section.min_card_count`を
  削除。`PageRange`のバリデーションを`end_page <= start_page`→`end_page < start_page`
  （ゼロ長レンジを許容）に緩和。
- `backend/tests/domain/test_section.py`・`test_generation_job.py`：上記変更に追従。
- `backend/tests/repositories/pdf/test_pdf_structure_repository.py`（全面書き換え）：
  純粋関数テスト、フェイクTOCによる階層構築アルゴリズムのテスト、`doc.set_toc()`で
  組み立てた実PDFによるエンドツーエンドテストの3層構成。

## 実装中に発見したバグ・問題点

実装の過程で、旧`pdf_parser.py`を「移植」する前提のまま進めていた際に、以下の問題を
実測で発見した（最終的にはTOCオンリー方式への転換によりほぼ全て解消済み）。

1. **`_kanji_to_arabic`の桁上げバグ**：旧実装は「十」「十X」（10〜19）のみを特別扱いし、
   「二十」「三十」等（20以上）は汎用の文字置換ループに落ちて`"210"`のような誤った文字列
   になっていた。今回インプットする教材は40章規模になる想定だったため、実測（
   `python3 -c "from ...pdf_structure_repository import _kanji_to_arabic; ..."`）で
   再現・修正した。最終的にはTOCオンリー化に伴い`_kanji_to_arabic`自体を削除した
   （実データに漢数字タイトルが1件も存在しなかったため）。
2. **`_find_visual_header`の1ブロック失敗が全ページの検出を無効化するバグ**：ある行の
   `spans`が空リストだと`min()`が`ValueError`を送出し、関数全体を覆う`try/except`が
   ページ全体の検出結果を`None`にしてしまっていた。PyMuPDFのブロック構造を模したモック
   オブジェクトで再現し、try/exceptをブロック単位に絞る修正で解消した。最終的には
   `_find_visual_header`自体をTOCオンリー化に伴い削除した。
3. **`_count_ranks_in_text`の先頭マッチ未カウントバグ**：`last_end=-1`の初期値により、
   最初のランクタグが文字位置49以前に出現すると（後続マッチとの距離に関わらず）一切
   カウントされない構造的な問題を実測で発見した。旧実装をそのまま移植した結果であり、
   コメントが示す意図（同一論点は1件として数える）と実装が食い違っていた。この機能は
   最終的に完全撤去（ADR 0001参照）となったため、修正は不要になった。
4. **設計の全面見直し**：実際にインプットする7冊のPDFの`doc.get_toc()`を確認した結果、
   「章→節の固定2階層」という前提が科目によって成立しないこと（管理会計論はフラット
   1階層、財務会計論は「部→章」）、TOCが全ファイルで正確に整備されていること、最低
   カード枚数の自動算出が実運用で使われていなかったことが判明し、Phase2-1の設計を
   TOCベース・可変階層・min_card_count完全撤去の方針に転換した。詳細は
   [ADR 0001](../adr/0001-pdf-structure-detection-toc-only.md)を参照。

## 大きな判断とその理由

上記4番の設計転換がPhase2-1における最大の判断であり、[ADR 0001](../adr/0001-pdf-structure-detection-toc-only.md)
として記録した。要点は「実データに合わせてTOCオンリー・可変階層に転換し、実運用で
使われていなかったmin_card_count機能を撤去した」こと。

## 動作確認

- サンドボックス環境にはPyMuPDFが無いため、`fitz`をスタブ化した上でテストファイルと
  同一のロジックを直接実行し、純粋関数（`_normalize_digits`/`_normalize_title`）と
  階層構築アルゴリズム（`_build_sections_from_toc`/`_finalize`）については実装時に
  Claude Code側で検証済み。
- 実PyMuPDFが必要な部分（`scan()`のエンドツーエンド、`extract_text_from_range`、
  `PdfParsingError`）は開発者の実機で
  `docker compose run --rm backend sh -c "pip install -e .[dev] && pytest"`を実行し、
  **54 passed**を確認済み。

## ADR

[ADR 0001: PDF構造検出をTOCベース・可変階層方式に変更し、最低カード枚数の自動算出を撤去する](../adr/0001-pdf-structure-detection-toc-only.md)
