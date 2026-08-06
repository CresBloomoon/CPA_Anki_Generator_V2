import json

import pytest

from app.repositories.ai.json_repair import CardJsonRepairError, extract_cards_from_json


class TestExtractCardsFromJson:
    def test_well_formed_json(self) -> None:
        raw = json.dumps({"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}]})
        cards = extract_cards_from_json(raw)
        assert cards[0]["TITLE"] == "A"
        assert cards[0]["TAGS"] == []

    def test_wrapped_in_markdown_fence(self) -> None:
        raw = json.dumps({"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}]})
        fenced = f"```json\n{raw}\n```"
        cards = extract_cards_from_json(fenced)
        assert cards[0]["TITLE"] == "A"

    def test_truncated_mid_array_recovers_completed_card(self) -> None:
        truncated = (
            '{"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"}, '
            '{"TITLE": "B", "PAGE_CODE": "1-1-2"'
        )
        cards = extract_cards_from_json(truncated)
        assert cards[0]["TITLE"] == "A"

    def test_truncated_with_trailing_comma_recovers(self) -> None:
        truncated = '{"cards": [{"TITLE": "A", "PAGE_CODE": "1-1-1"},'
        cards = extract_cards_from_json(truncated)
        assert cards[0]["TITLE"] == "A"

    def test_bare_array_with_two_cards_recovers_both(self) -> None:
        raw = json.dumps(
            [
                {"TITLE": "C", "PAGE_CODE": "1-1-3"},
                {"TITLE": "D", "PAGE_CODE": "1-1-4"},
            ]
        )
        cards = extract_cards_from_json(raw)
        assert [c["TITLE"] for c in cards] == ["C", "D"]

    def test_bare_array_with_single_card_is_not_silently_lost(self) -> None:
        # Regression test: brace-priority extraction used to land on exactly
        # one valid JSON object here, json.loads succeeded, and
        # data.get("cards", []) silently returned [] because there was no
        # "cards" key -- discarding the one real card with no error at all.
        raw = json.dumps([{"TITLE": "C", "PAGE_CODE": "1-1-3"}])
        cards = extract_cards_from_json(raw)
        assert len(cards) == 1
        assert cards[0]["TITLE"] == "C"

    def test_single_valid_object_buried_in_garbage_is_not_silently_lost(self) -> None:
        raw = 'garbage {"TITLE": "D", "PAGE_CODE": "1-1-4"} more garbage {bad json here'
        cards = extract_cards_from_json(raw)
        assert len(cards) == 1
        assert cards[0]["TITLE"] == "D"

    def test_explicit_empty_cards_list_stays_empty(self) -> None:
        # A deliberate {"cards": []} must not be confused with the
        # missing-key case above -- both are valid "the AI produced [nothing
        # unusual, but] zero cards" states in general, but this one is an
        # explicit, well-formed response and must be trusted as-is.
        raw = json.dumps({"cards": []})
        assert extract_cards_from_json(raw) == []

    def test_totally_unparseable_raises(self) -> None:
        with pytest.raises(CardJsonRepairError):
            extract_cards_from_json("not json at all")
