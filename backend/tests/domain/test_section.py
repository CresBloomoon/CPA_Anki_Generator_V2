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

    def test_child_with_blank_segment_still_raises(self) -> None:
        # .child() builds from already-known-good pieces, so it must stay
        # strict even though from_string() below is lenient about the same
        # kind of malformed input.
        root = DeckPath.from_string("公認会計士試験")
        with pytest.raises(ValueError):
            root.child("  ")

    def test_child_with_embedded_separator_still_raises(self) -> None:
        root = DeckPath.from_string("公認会計士試験")
        with pytest.raises(ValueError):
            root.child("財務会計論::理論")


class TestDeckPathFromString:
    def test_trailing_separator_is_dropped(self) -> None:
        # The exact shape of Phase5-3's default root path input value.
        assert DeckPath.from_string("公認会計士試験::").joined() == "公認会計士試験"

    def test_leading_separator_is_dropped(self) -> None:
        assert DeckPath.from_string("::公認会計士試験").joined() == "公認会計士試験"

    def test_doubled_separator_collapses(self) -> None:
        assert DeckPath.from_string("A::::B").joined() == "A::B"

    def test_surrounding_and_internal_whitespace_is_stripped(self) -> None:
        assert DeckPath.from_string("  A  ::  B  ").joined() == "A::B"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath.from_string("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath.from_string("   ")

    def test_separator_only_raises(self) -> None:
        with pytest.raises(ValueError):
            DeckPath.from_string("::")


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
