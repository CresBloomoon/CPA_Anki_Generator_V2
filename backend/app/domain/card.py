from __future__ import annotations

from dataclasses import dataclass

from app.domain.section import DeckPath

# Composite identity keys join TITLE and section_title with this separator.
# It is a non-printable control character that cannot appear in real card
# text, which guarantees Card("AB", "C") and Card("A", "BC") never collide
# (unlike the legacy implementation's plain string concatenation).
_IDENTITY_KEY_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class CardContentItem:
    title: str
    question: str
    ronsho_body: str
    kaisetsu_body: str
    yo_suruni_body: str
    ryui_body: str
    rank_tanto: str
    rank_ronbun: str
    page_code: str
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.page_code.strip():
            raise ValueError("page_code must not be empty")


@dataclass(frozen=True)
class CardContent:
    items: tuple[CardContentItem, ...]


@dataclass(frozen=True)
class Card:
    content: CardContentItem
    section_title: str
    deck_path: DeckPath

    def __post_init__(self) -> None:
        if not self.section_title.strip():
            raise ValueError("section_title must not be empty")

    def identity_key(self) -> str:
        return f"{self.content.title}{_IDENTITY_KEY_SEPARATOR}{self.section_title}"
