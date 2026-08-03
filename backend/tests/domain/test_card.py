import pytest

from app.domain.card import Card, CardContent, CardContentItem
from app.domain.section import DeckPath


def _make_item(**overrides: object) -> CardContentItem:
    defaults: dict[str, object] = {
        "title": "会計の意義",
        "question": "会計の意義について述べよ。",
        "ronsho_body": "論証本文",
        "kaisetsu_body": "解説本文",
        "yo_suruni_body": "要するに本文",
        "ryui_body": "特になし",
        "rank_tanto": "A",
        "rank_ronbun": "B",
        "page_code": "③-8-1",
        "tags": ("chap01", "tanto:A"),
    }
    defaults.update(overrides)
    return CardContentItem(**defaults)  # type: ignore[arg-type]


class TestCardContentItem:
    def test_valid_item_constructs(self) -> None:
        item = _make_item()
        assert item.page_code == "③-8-1"

    def test_empty_page_code_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_item(page_code="")

    def test_blank_page_code_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_item(page_code="  ")


class TestCardContent:
    def test_holds_multiple_items(self) -> None:
        content = CardContent(items=(_make_item(), _make_item(title="別の論点")))
        assert len(content.items) == 2


class TestCard:
    def _make_card(self, **overrides: object) -> Card:
        defaults: dict[str, object] = {
            "content": _make_item(),
            "section_title": "01節 会計の意義",
            "deck_path": DeckPath.from_string("公認会計士試験::財務会計論::01章 総論"),
        }
        defaults.update(overrides)
        return Card(**defaults)  # type: ignore[arg-type]

    def test_empty_section_title_raises(self) -> None:
        with pytest.raises(ValueError):
            self._make_card(section_title="")

    def test_identity_key_does_not_collide_across_boundary(self) -> None:
        card_ab_c = self._make_card(
            content=_make_item(title="AB"), section_title="C"
        )
        card_a_bc = self._make_card(
            content=_make_item(title="A"), section_title="BC"
        )
        assert card_ab_c.identity_key() != card_a_bc.identity_key()

    def test_identity_key_is_stable_for_same_inputs(self) -> None:
        card1 = self._make_card()
        card2 = self._make_card()
        assert card1.identity_key() == card2.identity_key()
