import pytest

from app.domain.section import DeckPath, PageRange, Section


class TestPageRange:
    def test_start_page_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRange(start_page=0)

    def test_end_page_less_than_start_page_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRange(start_page=5, end_page=4)

    def test_end_page_equal_to_start_page_is_allowed(self) -> None:
        # A TOC entry can legitimately share its start page with the very
        # next entry (e.g. a part heading and its first chapter on the same
        # page), yielding a zero-length range.
        page_range = PageRange(start_page=5, end_page=5)
        assert page_range.page_count() == 0

    def test_page_count_with_known_end_page(self) -> None:
        assert PageRange(start_page=3, end_page=8).page_count() == 5

    def test_page_count_without_end_page_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRange(start_page=3).page_count()


class TestDeckPath:
    def test_empty_segments_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath(())

    def test_blank_segment_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath(("公認会計士試験", "  "))

    def test_segment_containing_separator_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath(("公認会計士試験::財務会計論",))

    def test_child_appends_segment(self) -> None:
        root = DeckPath.from_string("公認会計士試験::財務会計論")
        result = root.child("01章 総論").child("01節 会計の意義")
        assert result.joined() == "公認会計士試験::財務会計論::01章 総論::01節 会計の意義"


class TestSection:
    def _make_section(self, **overrides: object) -> Section:
        defaults: dict[str, object] = {
            "title": "01節 会計の意義",
            "page_range": PageRange(start_page=1, end_page=5),
            "deck_path": DeckPath.from_string("公認会計士試験::財務会計論"),
            "source_file": "textbook.pdf",
        }
        defaults.update(overrides)
        return Section(**defaults)  # type: ignore[arg-type]

    def test_valid_section_constructs(self) -> None:
        section = self._make_section()
        assert section.title == "01節 会計の意義"

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError):
            self._make_section(title="  ")

    def test_empty_source_file_raises(self) -> None:
        with pytest.raises(ValueError):
            self._make_section(source_file="")
