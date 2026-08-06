from __future__ import annotations

from app.domain.card import Card
from app.domain.deck import Deck

# The 9 genanki Model fields, in the exact order the card templates'
# {{FIELD}} placeholders expect. TAGS is intentionally excluded -- it maps
# to genanki Note tags, not a field.
FIELD_NAMES = [
    "TITLE",
    "QUESTION",
    "RONSHO_BODY",
    "KAISETSU_BODY",
    "YO_SURUNI_BODY",
    "RYUI_BODY",
    "RANK_TANTO",
    "RANK_RONBUN",
    "PAGE_CODE",
]

_TAG_WHITESPACE_CHARS = (" ", "　")


def sanitize_tag(tag: str) -> str:
    sanitized = tag
    for char in _TAG_WHITESPACE_CHARS:
        sanitized = sanitized.replace(char, "_")
    return sanitized


def build_note_tags(card: Card) -> list[str]:
    tags = [sanitize_tag(tag) for tag in card.content.tags]
    tags.append(sanitize_tag(card.section_title))
    return tags


def build_note_fields(card: Card) -> list[str]:
    item = card.content
    return [
        item.title,
        item.question,
        item.ronsho_body,
        item.kaisetsu_body,
        item.yo_suruni_body,
        item.ryui_body,
        item.rank_tanto,
        item.rank_ronbun,
        item.page_code,
    ]


def group_cards_into_decks(cards: list[Card]) -> list[Deck]:
    decks_by_path: dict[str, Deck] = {}
    for card in cards:
        key = card.deck_path.joined()
        if key not in decks_by_path:
            decks_by_path[key] = Deck(deck_path=card.deck_path)
        decks_by_path[key].add_card(card)
    return list(decks_by_path.values())
