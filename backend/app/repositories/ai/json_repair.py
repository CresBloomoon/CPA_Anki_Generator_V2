from __future__ import annotations

import json
import re

# The AI is instructed to return only JSON, but in practice a response can be
# wrapped in a markdown code fence, or get cut off mid-generation when the
# model hits its output limit. This module ports the legacy ai_client.py's
# best-effort recovery for both cases before giving up.

_CARD_FIELD_DEFAULTS: dict[str, object] = {
    "TITLE": "",
    "QUESTION": "",
    "RONSHO_BODY": "",
    "KAISETSU_BODY": "",
    "YO_SURUNI_BODY": "",
    "RYUI_BODY": "",
    "RANK_TANTO": "",
    "RANK_RONBUN": "",
    "PAGE_CODE": "",
    "TAGS": [],
}

_FLAT_OBJECT_PATTERN = re.compile(r"\{[^{}]*\}")


class CardJsonRepairError(Exception):
    """Raised when card JSON cannot be recovered from the AI response."""


def _format_cards(raw_cards: list[dict]) -> list[dict]:
    return [
        {key: card.get(key, default) for key, default in _CARD_FIELD_DEFAULTS.items()}
        for card in raw_cards
    ]


def _repair_truncated_json(json_str: str) -> str:
    if json_str.strip().endswith("}"):
        return json_str

    if '"cards": [' in json_str:
        repaired = json_str.strip()
        if repaired.endswith(","):
            repaired = repaired[:-1]
        if not repaired.endswith("]"):
            repaired += " ]"
        if not repaired.endswith("}"):
            repaired += " }"
        return repaired

    if json_str.strip().startswith("["):
        repaired = json_str.strip()
        if repaired.endswith(","):
            repaired = repaired[:-1]
        repaired += " ]"
        return repaired

    return json_str


def extract_cards_from_json(raw: str) -> list[dict]:
    text = raw.replace("```json", "").replace("```", "").strip()

    start_brace = text.find("{")
    end_brace = text.rfind("}")
    start_bracket = text.find("[")
    end_bracket = text.rfind("]")

    if start_brace != -1 and end_brace > start_brace:
        json_str = text[start_brace : end_brace + 1]
    elif start_bracket != -1 and end_bracket > start_bracket:
        json_str = '{"cards": ' + text[start_bracket : end_bracket + 1] + "}"
    else:
        json_str = text

    json_str = _repair_truncated_json(json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return _recover_via_flat_objects(json_str)

    if isinstance(data, dict) and "cards" not in data:
        # json.loads succeeded, but the AI returned a bare object/array
        # instead of the instructed {"cards": [...]} wrapper (e.g. the
        # brace-priority extraction above happened to land on exactly one
        # valid object). Treating a missing key the same as an
        # intentionally empty "cards": [] would silently discard a real
        # card, so fall back to the same recovery used for malformed JSON.
        return _recover_via_flat_objects(json_str)

    return _format_cards(data.get("cards", []))


def _recover_via_flat_objects(json_str: str) -> list[dict]:
    # Last resort: pull out whatever flat (non-nested) {...} objects can be
    # individually parsed, skipping any that still fail.
    matches = _FLAT_OBJECT_PATTERN.findall(json_str)
    if matches:
        potential_cards = []
        for match in matches:
            try:
                potential_cards.append(json.loads(match))
            except json.JSONDecodeError:
                continue
        return _format_cards(potential_cards)
    raise CardJsonRepairError(
        "AI応答からカードJSONを抽出できませんでした（修復も失敗しました）"
    )
