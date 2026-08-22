from app.domain.card import CardContentItem
from app.repositories.ai.card_content_mapper import to_card_content_item


class TestToCardContentItem:
    def test_maps_all_fields(self) -> None:
        item = to_card_content_item(
            {
                "TITLE": "t",
                "QUESTION": "q",
                "RONSHO_BODY": "r",
                "KAISETSU_BODY": "k",
                "YO_SURUNI_BODY": "y",
                "RYUI_BODY": "ry",
                "RANK_TANTO": "A",
                "RANK_RONBUN": "B",
                "PAGE_CODE": "1-1-1",
                "TAGS": ["a", "b"],
            }
        )

        assert item == CardContentItem(
            title="t",
            question="q",
            ronsho_body="r",
            kaisetsu_body="k",
            yo_suruni_body="y",
            ryui_body="ry",
            rank_tanto="A",
            rank_ronbun="B",
            page_code="1-1-1",
            tags=("a", "b"),
        )

    def test_missing_fields_default_to_empty_string_or_no_tags(self) -> None:
        item = to_card_content_item({"PAGE_CODE": "1-1-1"})

        assert item.title == ""
        assert item.tags == ()

    def test_comma_separated_string_tags_are_split_and_trimmed(self) -> None:
        item = to_card_content_item({"PAGE_CODE": "1-1-1", "TAGS": "a, b ,c"})

        assert item.tags == ("a", "b", "c")
