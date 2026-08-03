from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.domain.card import Card
from app.domain.section import DeckPath


def deterministic_deck_id(deck_path: DeckPath) -> int:
    # The legacy implementation used Python's built-in hash(), which is
    # randomized per-process (PYTHONHASHSEED) unless explicitly fixed, so the
    # same deck path produced a different Anki deck ID on every run. MD5 has
    # no such randomization, so the same deck_path always maps to the same
    # ID, which is what makes re-importing a regenerated .apkg update an
    # existing deck instead of creating a duplicate.
    digest = hashlib.md5(deck_path.joined().encode("utf-8")).hexdigest()
    return int(digest, 16) % (10**10)


@dataclass
class Deck:
    deck_path: DeckPath
    cards: list[Card] = field(default_factory=list)

    def add_card(self, card: Card) -> None:
        if card.deck_path != self.deck_path:
            raise ValueError(
                f"card deck_path {card.deck_path.joined()!r} does not match "
                f"deck deck_path {self.deck_path.joined()!r}"
            )
        self.cards.append(card)
