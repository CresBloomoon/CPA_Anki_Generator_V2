from __future__ import annotations

from app.domain.card import CardContentItem

# Shared by every AiCardGeneratorRepository implementation (Gemini/Claude/
# ChatGPT): converts one raw card dict (however it was extracted --
# JSON-parsed text for Gemini, an already-parsed tool_use.input for Claude,
# a schema-validated JSON string for ChatGPT) into the common domain type.
# This mapping itself has no provider-specific branching, unlike the
# retry/error-classification logic in each repository, which stays
# independent per Phase2-8/2-9's design discussion.


def to_card_content_item(raw_card: dict) -> CardContentItem:
    tags = raw_card.get("TAGS", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    return CardContentItem(
        title=raw_card.get("TITLE", ""),
        question=raw_card.get("QUESTION", ""),
        ronsho_body=raw_card.get("RONSHO_BODY", ""),
        kaisetsu_body=raw_card.get("KAISETSU_BODY", ""),
        yo_suruni_body=raw_card.get("YO_SURUNI_BODY", ""),
        ryui_body=raw_card.get("RYUI_BODY", ""),
        rank_tanto=raw_card.get("RANK_TANTO", ""),
        rank_ronbun=raw_card.get("RANK_RONBUN", ""),
        page_code=raw_card.get("PAGE_CODE", ""),
        tags=tuple(tags),
    )
