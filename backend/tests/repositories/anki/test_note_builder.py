from app.domain.card import Card, CardContentItem
from app.domain.section import DeckPath
from app.repositories.anki.note_builder import (
    FIELD_NAMES,
    build_note_fields,
    build_note_tags,
    group_cards_into_decks,
    sanitize_tag,
)


def _make_card(
    title: str = "会計の意義",
    section_title: str = "01節 会計の意義",
    deck_path: DeckPath | None = None,
    tags: tuple[str, ...] = (),
) -> Card:
    item = CardContentItem(
        title=title,
        question="Q",
        ronsho_body="R",
        kaisetsu_body="K",
        yo_suruni_body="Y",
        ryui_body="特になし",
        rank_tanto="A",
        rank_ronbun="B",
        page_code="③-8-1",
        tags=tags,
    )
    return Card(
        content=item,
        section_title=section_title,
        deck_path=deck_path or DeckPath.from_string("公認会計士試験::財務会計論"),
    )


class TestSanitizeTag:
    def test_replaces_half_width_space(self) -> None:
        assert sanitize_tag("tanto A") == "tanto_A"

    def test_replaces_full_width_space(self) -> None:
        assert sanitize_tag("tanto　A") == "tanto_A"

    def test_leaves_tag_without_spaces_unchanged(self) -> None:
        assert sanitize_tag("chap01") == "chap01"


class TestBuildNoteFields:
    def test_returns_fields_in_field_names_order(self) -> None:
        card = _make_card()
        fields = build_note_fields(card)

        assert len(fields) == len(FIELD_NAMES)
        assert fields[FIELD_NAMES.index("TITLE")] == "会計の意義"
        assert fields[FIELD_NAMES.index("PAGE_CODE")] == "③-8-1"
        assert fields[FIELD_NAMES.index("RANK_TANTO")] == "A"


class TestBuildNoteTags:
    def test_includes_sanitized_content_tags(self) -> None:
        card = _make_card(tags=("chap01", "tanto:A"))
        tags = build_note_tags(card)
        assert "chap01" in tags
        assert "tanto:A" in tags

    def test_appends_sanitized_section_title_as_a_tag(self) -> None:
        card = _make_card(section_title="01節 会計の意義")
        tags = build_note_tags(card)
        assert "01節_会計の意義" in tags

    def test_section_title_is_always_appended_even_without_content_tags(self) -> None:
        card = _make_card(tags=())
        tags = build_note_tags(card)
        assert len(tags) == 1


class TestGroupCardsIntoDecks:
    def test_groups_cards_sharing_the_same_deck_path(self) -> None:
        deck_path = DeckPath.from_string("A::B")
        card1 = _make_card(title="t1", deck_path=deck_path)
        card2 = _make_card(title="t2", deck_path=deck_path)

        decks = group_cards_into_decks([card1, card2])

        assert len(decks) == 1
        assert len(decks[0].cards) == 2

    def test_separates_cards_with_different_deck_paths(self) -> None:
        card1 = _make_card(title="t1", deck_path=DeckPath.from_string("A::B"))
        card2 = _make_card(title="t2", deck_path=DeckPath.from_string("A::C"))

        decks = group_cards_into_decks([card1, card2])

        assert len(decks) == 2
        joined_paths = {deck.deck_path.joined() for deck in decks}
        assert joined_paths == {"A::B", "A::C"}

    def test_empty_input_returns_no_decks(self) -> None:
        assert group_cards_into_decks([]) == []
