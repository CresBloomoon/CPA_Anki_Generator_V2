from __future__ import annotations

import os
import tempfile
from pathlib import Path

import genanki

from app.domain.card import Card
from app.domain.deck import deterministic_deck_id
from app.repositories.anki.note_builder import (
    FIELD_NAMES,
    build_note_fields,
    build_note_tags,
    group_cards_into_decks,
)

_APP_DIR = Path(__file__).resolve().parents[2]
_CARD_TEMPLATES_DIR = _APP_DIR / "card_templates"
_ASSETS_DIR = _CARD_TEMPLATES_DIR / "assets"

# Fixed so re-importing a regenerated .apkg updates the existing note type
# instead of creating a duplicate. Chosen independently from the legacy
# app's model_id (1598273645) -- V2's GUID computation differs (see
# Card.identity_key), so there is no benefit to reusing the old ID, and a
# fresh one avoids any ambiguity if the two field layouts ever diverge.
_MODEL_ID = 663778992
_MODEL_NAME = "CPA Anki Generator V2"


class AnkiPackageRepository:
    def __init__(
        self,
        card_templates_dir: Path = _CARD_TEMPLATES_DIR,
        assets_dir: Path = _ASSETS_DIR,
    ) -> None:
        self._front_html = (
            card_templates_dir / "anki_front_card_template.html"
        ).read_text(encoding="utf-8")
        self._back_html = (
            card_templates_dir / "anki_back_card_template.html"
        ).read_text(encoding="utf-8")
        self._css = (card_templates_dir / "anki_card_style.css").read_text(
            encoding="utf-8"
        )
        self._assets_dir = assets_dir

    def build_package(self, cards: list[Card]) -> bytes:
        model = self._build_model()
        decks = group_cards_into_decks(cards)

        genanki_decks = []
        for deck in decks:
            genanki_deck = genanki.Deck(
                deterministic_deck_id(deck.deck_path), deck.deck_path.joined()
            )
            for card in deck.cards:
                genanki_deck.add_note(self._build_note(model, card))
            genanki_decks.append(genanki_deck)

        package = genanki.Package(genanki_decks)
        package.media_files = self._media_file_paths()

        return self._serialize(package)

    def _build_model(self) -> genanki.Model:
        return genanki.Model(
            _MODEL_ID,
            _MODEL_NAME,
            fields=[{"name": name} for name in FIELD_NAMES],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": self._front_html,
                    "afmt": self._back_html,
                }
            ],
            css=self._css,
        )

    def _build_note(self, model: genanki.Model, card: Card) -> genanki.Note:
        return genanki.Note(
            model=model,
            fields=build_note_fields(card),
            tags=build_note_tags(card),
            guid=genanki.guid_for(card.identity_key()),
        )

    def _media_file_paths(self) -> list[str]:
        candidates = [
            self._assets_dir / "_html2canvas.js",
            self._assets_dir / "_success_icon.png",
        ]
        return [str(path) for path in candidates if path.exists()]

    def _serialize(self, package: genanki.Package) -> bytes:
        fd, temp_path_str = tempfile.mkstemp(suffix=".apkg")
        os.close(fd)
        temp_path = Path(temp_path_str)
        try:
            package.write_to_file(str(temp_path))
            return temp_path.read_bytes()
        finally:
            temp_path.unlink(missing_ok=True)
