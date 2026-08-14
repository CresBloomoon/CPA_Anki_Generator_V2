from app.routes.page_range_display import to_display_end_page, to_internal_end_page


class TestToDisplayEndPage:
    def test_none_stays_none(self) -> None:
        assert to_display_end_page(None) is None

    def test_subtracts_one(self) -> None:
        # Internal (exclusive, next section's start_page) 62 -> displayed
        # as this section's own last page, 61.
        assert to_display_end_page(62) == 61


class TestToInternalEndPage:
    def test_none_stays_none(self) -> None:
        assert to_internal_end_page(None) is None

    def test_adds_one(self) -> None:
        assert to_internal_end_page(61) == 62


class TestRoundTrip:
    def test_display_then_internal_returns_the_original_value(self) -> None:
        original = 62
        assert to_internal_end_page(to_display_end_page(original)) == original
