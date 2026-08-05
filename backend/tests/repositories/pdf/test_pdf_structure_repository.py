import fitz
import pytest

from app.repositories.pdf.pdf_structure_repository import (
    PdfParsingError,
    PdfStructureRepository,
    _normalize_digits,
    _normalize_title,
)

# --- Pure-function tests --------------------------------------------------


class TestNormalizeDigits:
    def test_converts_zenkaku_to_hankaku(self) -> None:
        assert _normalize_digits("１２３") == "123"


class TestNormalizeTitle:
    def test_zero_pads_zenkaku_chapter_number(self) -> None:
        assert _normalize_title("第４章　資産会計") == "第04章　資産会計"

    def test_zero_pads_zenkaku_part_number(self) -> None:
        assert _normalize_title("第１部 コンプリートチェック") == "第01部 コンプリートチェック"

    def test_leaves_already_two_digit_number_unchanged(self) -> None:
        # Real sample data mixes zenkaku (1-9) and hankaku (10+) digits
        # within the same book; 10+ is already unambiguous and needs no
        # further padding.
        title = "第10節 監査の過程で識別した虚偽表示の評価"
        assert _normalize_title(title) == title

    def test_handles_chapter_numbers_up_to_the_observed_maximum(self) -> None:
        # 財務会計論's sample material goes up to chapter 24.
        assert _normalize_title("第24章 リース") == "第24章 リース"

    def test_titles_without_a_leading_dai_prefix_pass_through_unchanged(self) -> None:
        assert _normalize_title("目次") == "目次"
        assert _normalize_title("＜はじめに＞") == "＜はじめに＞"
        assert _normalize_title("序章") == "序章"
        assert _normalize_title("補章 直近の過去問解説") == "補章 直近の過去問解説"

    def test_kanji_numeral_titles_pass_through_unchanged_without_crashing(self) -> None:
        # No kanji-numeral titles were observed in the 7 sample PDFs, but a
        # future book might use them. _normalize_title must not raise or
        # mangle text it doesn't recognize -- it should just leave it as-is.
        assert _normalize_title("第四章 総論") == "第四章 総論"


# --- Hierarchy-building algorithm tests (fake TOC, no real PDF needed) ----


class _FakeDoc:
    def __init__(self, toc: list[tuple[int, str, int]], page_count: int) -> None:
        self._toc = toc
        self.page_count = page_count

    def get_toc(self) -> list[tuple[int, str, int]]:
        return self._toc


class TestBuildSectionsFromToc:
    def test_part_chapter_hierarchy_disambiguates_duplicate_titles(self) -> None:
        # Mirrors the real 財務会計論 sample: the same chapter title repeats
        # under two different parts, and a noise entry (目次) shares a page
        # with the first part heading.
        toc = [
            (1, "目次", 3),
            (1, "第１部 コンプリートチェック", 3),
            (2, "第１章 財務会計の基礎概念", 16),
            (2, "第２章 企業会計制度と会計基準", 30),
            (1, "第２部 スマートコアチェックplus", 142),
            (2, "第１章 財務会計の基礎概念", 143),
        ]
        repo = PdfStructureRepository()
        sections = repo._build_sections_from_toc(_FakeDoc(toc, page_count=200))

        assert [s.title for s in sections] == [
            "目次",
            "第01部 コンプリートチェック",
            "第01章 財務会計の基礎概念",
            "第02章 企業会計制度と会計基準",
            "第02部 スマートコアチェックplus",
            "第01章 財務会計の基礎概念",
        ]
        assert sections[0].ancestors == ()  # 目次: no parent
        assert sections[1].ancestors == ()  # 第01部: top level
        assert sections[2].ancestors == ("第01部 コンプリートチェック",)
        assert sections[3].ancestors == ("第01部 コンプリートチェック",)
        assert sections[4].ancestors == ()
        # Same title, different part -> disambiguated by ancestors.
        assert sections[5].ancestors == ("第02部 スマートコアチェックplus",)
        assert sections[2].ancestors != sections[5].ancestors

    def test_flat_single_level_hierarchy_has_no_ancestors(self) -> None:
        # Mirrors 管理会計論: no sub-level exists at all.
        toc = [
            (1, "目次", 2),
            (1, "第１章 原価計算の基礎知識", 4),
            (1, "第２章 費目別計算", 62),
        ]
        repo = PdfStructureRepository()
        sections = repo._build_sections_from_toc(_FakeDoc(toc, page_count=100))

        assert [s.ancestors for s in sections] == [(), (), ()]
        assert [s.level for s in sections] == [1, 1, 1]


class TestFinalize:
    def test_end_page_is_the_next_entrys_start_page(self) -> None:
        toc = [(1, "第01章 総論", 1), (1, "第02章 資産会計", 10)]
        repo = PdfStructureRepository()
        pending = repo._build_sections_from_toc(_FakeDoc(toc, page_count=50))
        warnings: list[str] = []
        sections = repo._finalize(pending, source_file="x.pdf", warnings=warnings)

        assert sections[0].page_range.start_page == 1
        assert sections[0].page_range.end_page == 10
        assert sections[1].page_range.end_page is None
        assert warnings == []

    def test_same_start_page_yields_a_zero_length_range(self) -> None:
        # Confirmed in real sample data: a part heading and its following
        # entry (目次, or its first chapter) can share the same page.
        toc = [(1, "目次", 3), (1, "第01部 総論", 3)]
        repo = PdfStructureRepository()
        pending = repo._build_sections_from_toc(_FakeDoc(toc, page_count=50))
        sections = repo._finalize(pending, source_file="x.pdf", warnings=[])

        assert sections[0].page_range.start_page == 3
        assert sections[0].page_range.end_page == 3
        assert sections[0].page_range.page_count() == 0

    def test_non_monotonic_toc_pages_fall_back_to_open_ended_with_a_warning(
        self,
    ) -> None:
        # A malformed TOC where the next entry's page precedes this one's
        # must not crash the scan.
        toc = [(1, "第01章 A", 10), (1, "第02章 B", 5)]
        repo = PdfStructureRepository()
        pending = repo._build_sections_from_toc(_FakeDoc(toc, page_count=50))
        warnings: list[str] = []
        sections = repo._finalize(pending, source_file="x.pdf", warnings=warnings)

        assert sections[0].page_range.end_page is None
        assert len(warnings) == 1

    def test_source_file_is_stamped_on_every_section(self) -> None:
        toc = [(1, "第01章 A", 1)]
        repo = PdfStructureRepository()
        pending = repo._build_sections_from_toc(_FakeDoc(toc, page_count=10))
        sections = repo._finalize(pending, source_file="chapter04.pdf", warnings=[])

        assert all(s.source_file == "chapter04.pdf" for s in sections)


# --- End-to-end tests against real PyMuPDF documents ----------------------


def _build_fixture_pdf_with_toc() -> bytes:
    doc = fitz.open()
    for _ in range(6):
        doc.new_page(width=595, height=842)
    doc.set_toc(
        [
            [1, "目次", 1],
            [1, "第１部 コンプリートチェック", 1],
            [2, "第１章 財務会計の基礎概念", 2],
            [2, "第２章 企業会計制度と会計基準", 3],
            [1, "第２部 スマートコアチェックplus", 5],
            [2, "第１章 財務会計の基礎概念", 6],
        ]
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestScanEndToEnd:
    def test_scan_wires_up_toc_parsing_against_a_real_pdf(self) -> None:
        repository = PdfStructureRepository()
        result = repository.scan(_build_fixture_pdf_with_toc(), source_file="zaimu.pdf")

        assert [s.title for s in result.sections] == [
            "目次",
            "第01部 コンプリートチェック",
            "第01章 財務会計の基礎概念",
            "第02章 企業会計制度と会計基準",
            "第02部 スマートコアチェックplus",
            "第01章 財務会計の基礎概念",
        ]
        assert result.sections[2].ancestors == ("第01部 コンプリートチェック",)
        assert result.sections[5].ancestors == ("第02部 スマートコアチェックplus",)
        assert all(s.source_file == "zaimu.pdf" for s in result.sections)


class TestExtractTextFromRange:
    def _build_fixture_pdf_with_text(self) -> bytes:
        doc = fitz.open()
        for index in range(4):
            page = doc.new_page(width=595, height=842)
            page.insert_text((50, 100), f"PAGE {index + 1} CONTENT", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_extracts_text_with_page_markers(self) -> None:
        repository = PdfStructureRepository()
        text = repository.extract_text_from_range(
            self._build_fixture_pdf_with_text(), start_page=2, end_page=3
        )
        assert "--- ページ 2 ---" in text
        assert "PAGE 2 CONTENT" in text
        assert "--- ページ 3 ---" not in text

    def test_end_page_none_extracts_to_end_of_document(self) -> None:
        repository = PdfStructureRepository()
        text = repository.extract_text_from_range(
            self._build_fixture_pdf_with_text(), start_page=3
        )
        assert "--- ページ 3 ---" in text
        assert "--- ページ 4 ---" in text


class TestPdfParsingError:
    def test_scan_raises_on_invalid_pdf_bytes(self) -> None:
        repository = PdfStructureRepository()
        with pytest.raises(PdfParsingError):
            repository.scan(b"not a pdf", source_file="broken.pdf")

    def test_extract_text_raises_on_invalid_pdf_bytes(self) -> None:
        repository = PdfStructureRepository()
        with pytest.raises(PdfParsingError):
            repository.extract_text_from_range(b"not a pdf", start_page=1)
