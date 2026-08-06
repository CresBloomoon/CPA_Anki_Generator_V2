import json
import os
import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import genanki

from app.domain.card import Card, CardContentItem
from app.domain.deck import deterministic_deck_id
from app.domain.section import DeckPath
from app.repositories.anki.anki_package_repository import AnkiPackageRepository


def _make_card(
    title: str = "会計の意義",
    section_title: str = "01節 会計の意義",
    deck_path: DeckPath | None = None,
    tags: tuple[str, ...] = (),
) -> Card:
    item = CardContentItem(
        title=title,
        question="会計の意義について述べよ。",
        ronsho_body="論証本文",
        kaisetsu_body="解説本文",
        yo_suruni_body="要するに本文",
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


def _extract_collection_rows(package_bytes: bytes) -> list[tuple[str, str, str]]:
    """Returns (flds, tags, guid) for every note in the generated .apkg."""
    with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
        db_bytes = archive.read("collection.anki2")

    fd, db_path_str = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    db_path = Path(db_path_str)
    try:
        db_path.write_bytes(db_bytes)
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute("SELECT flds, tags, guid FROM notes").fetchall()
        finally:
            conn.close()
    finally:
        db_path.unlink(missing_ok=True)


def _extract_decks(package_bytes: bytes) -> dict[str, dict]:
    """Returns the parsed {deck_id_str: {"id": ..., "name": ..., ...}} map.

    Confirmed via real genanki output (Docker) that there is no separate
    "decks" table -- deck metadata is stored as a JSON blob in the
    single-row col table's "decks" column, keyed by deck ID string.
    """
    with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
        db_bytes = archive.read("collection.anki2")

    fd, db_path_str = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    db_path = Path(db_path_str)
    try:
        db_path.write_bytes(db_bytes)
        conn = sqlite3.connect(db_path)
        try:
            (decks_raw,) = conn.execute("SELECT decks FROM col").fetchone()
            return json.loads(decks_raw)
        finally:
            conn.close()
    finally:
        db_path.unlink(missing_ok=True)


class TestBuildPackage:
    def test_produces_a_valid_apkg_zip(self) -> None:
        repository = AnkiPackageRepository()
        card = _make_card()

        package_bytes = repository.build_package([card])

        assert zipfile.is_zipfile(BytesIO(package_bytes))

    def test_note_fields_tags_and_guid_reach_the_collection(self) -> None:
        repository = AnkiPackageRepository()
        card = _make_card(
            title="会計の意義",
            section_title="01節 会計の意義",
            tags=("chap01", "tanto:A"),
        )

        package_bytes = repository.build_package([card])
        rows = _extract_collection_rows(package_bytes)

        assert len(rows) == 1
        flds, tags, guid = rows[0]
        fields = flds.split("\x1f")
        assert fields[0] == "会計の意義"  # TITLE is the first genanki field
        assert fields[-1] == "③-8-1"  # PAGE_CODE is the last field
        assert "chap01" in tags
        # section_title's half-width space must be sanitized to '_'
        assert "01節_会計の意義" in tags
        assert guid == genanki.guid_for(card.identity_key())

    def test_cards_with_different_deck_paths_produce_separate_decks(self) -> None:
        repository = AnkiPackageRepository()
        card1 = _make_card(title="t1", deck_path=DeckPath.from_string("Root::A"))
        card2 = _make_card(title="t2", deck_path=DeckPath.from_string("Root::B"))

        package_bytes = repository.build_package([card1, card2])
        rows = _extract_collection_rows(package_bytes)

        assert len(rows) == 2

    def test_deck_id_is_deterministic_not_process_random(self) -> None:
        # Regression guard for the legacy abs(hash(...)) bug: building the
        # same deck twice (even across separate calls) must not depend on
        # Python's randomized hash() seed.
        repository = AnkiPackageRepository()
        deck_path = DeckPath.from_string("Root::A")
        card = _make_card(deck_path=deck_path)

        repository.build_package([card])  # first build
        second_build_bytes = repository.build_package([card])  # second build

        decks = _extract_decks(second_build_bytes)
        matching = [
            deck_info
            for deck_info in decks.values()
            if deck_info["name"] == deck_path.joined()
        ]
        assert len(matching) == 1
        assert matching[0]["id"] == deterministic_deck_id(deck_path)

    def test_media_files_are_embedded_for_the_copy_to_clipboard_feature(self) -> None:
        repository = AnkiPackageRepository()
        card = _make_card()

        package_bytes = repository.build_package([card])

        with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
            manifest = json.loads(archive.read("media"))
            embedded_names = set(manifest.values())
            assert "_html2canvas.js" in embedded_names
            assert "_success_icon.png" in embedded_names

    def test_empty_card_list_still_produces_a_valid_apkg(self) -> None:
        repository = AnkiPackageRepository()

        package_bytes = repository.build_package([])

        assert zipfile.is_zipfile(BytesIO(package_bytes))
