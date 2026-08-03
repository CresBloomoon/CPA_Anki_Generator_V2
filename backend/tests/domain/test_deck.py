import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.card import Card, CardContentItem
from app.domain.deck import Deck, deterministic_deck_id
from app.domain.section import DeckPath

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _make_card(deck_path: DeckPath, title: str = "会計の意義") -> Card:
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
    )
    return Card(content=item, section_title="01節 会計の意義", deck_path=deck_path)


class TestDeterministicDeckId:
    def test_same_deck_path_yields_same_id(self) -> None:
        deck_path = DeckPath.from_string("公認会計士試験::財務会計論")
        assert deterministic_deck_id(deck_path) == deterministic_deck_id(deck_path)

    def test_different_deck_path_yields_different_id(self) -> None:
        first = deterministic_deck_id(DeckPath.from_string("公認会計士試験::財務会計論"))
        second = deterministic_deck_id(DeckPath.from_string("公認会計士試験::監査論"))
        assert first != second

    def test_stable_across_python_hash_seeds(self) -> None:
        # This is the regression test for the legacy bug: hash() is
        # randomized per-process via PYTHONHASHSEED, so a hash()-based ID
        # would differ across these subprocess runs even for the same
        # deck_path. deterministic_deck_id must not.
        script = (
            "from app.domain.deck import deterministic_deck_id\n"
            "from app.domain.section import DeckPath\n"
            "print(deterministic_deck_id(DeckPath.from_string('公認会計士試験::財務会計論')))\n"
        )
        results = set()
        for seed in ("0", "1", "12345"):
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=BACKEND_ROOT,
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=True,
            )
            results.add(completed.stdout.strip())
        assert len(results) == 1


class TestDeck:
    def test_add_card_appends_matching_card(self) -> None:
        deck_path = DeckPath.from_string("公認会計士試験::財務会計論")
        deck = Deck(deck_path=deck_path)
        card = _make_card(deck_path)

        deck.add_card(card)

        assert deck.cards == [card]

    def test_add_card_rejects_mismatched_deck_path(self) -> None:
        deck = Deck(deck_path=DeckPath.from_string("公認会計士試験::財務会計論"))
        mismatched_card = _make_card(DeckPath.from_string("公認会計士試験::監査論"))

        with pytest.raises(ValueError):
            deck.add_card(mismatched_card)
