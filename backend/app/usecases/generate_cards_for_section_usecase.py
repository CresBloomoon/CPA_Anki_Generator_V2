from __future__ import annotations

import re
from typing import Protocol

from app.domain.card import Card
from app.domain.section import Section
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.dto import PromptContext

# A section longer than this many pages gets split into blocks before being
# sent to the AI, so a single call is never given an overwhelming chunk of
# text at once.
_SPLIT_THRESHOLD_PAGES = 5
_MAX_PAGES_PER_BLOCK = 4

_PAGE_MARKER_PATTERN = re.compile(r"--- ページ \d+ ---")


class SupportsExtractText(Protocol):
    """What this usecase needs from a PDF structure repository.

    Defined as a structural Protocol (rather than importing the concrete
    PdfStructureRepository class) so this module -- and anything that tests
    it -- has no dependency on PyMuPDF.
    """

    def extract_text_from_range(
        self, pdf_bytes: bytes, start_page: int, end_page: int | None = None
    ) -> str: ...


class GenerateCardsForSectionUsecase:
    def __init__(
        self,
        pdf_structure_repository: SupportsExtractText,
        ai_repository: AiCardGeneratorRepository,
    ) -> None:
        self._pdf_structure_repository = pdf_structure_repository
        self._ai_repository = ai_repository

    def execute(self, section: Section, pdf_bytes: bytes) -> list[Card]:
        full_text = self._pdf_structure_repository.extract_text_from_range(
            pdf_bytes, section.page_range.start_page, section.page_range.end_page
        )
        blocks = self._group_into_blocks(self._split_into_pages(full_text))
        total_blocks = len(blocks)

        cards: list[Card] = []
        for position, block_pages in enumerate(blocks, start=1):
            prompt_context = PromptContext(
                section_title=section.title,
                block_index=position if total_blocks > 1 else None,
                block_count=total_blocks if total_blocks > 1 else None,
            )
            # Any failure here (AI error, unrecoverable JSON, ...) is
            # intentionally left to propagate -- deciding whether to abort
            # the rest of the job or keep sections already completed is
            # Phase3-3's job, not this usecase's.
            card_content = self._ai_repository.generate_cards(
                "".join(block_pages), prompt_context
            )
            for item in card_content.items:
                cards.append(
                    Card(
                        content=item,
                        section_title=section.title,
                        deck_path=section.deck_path,
                    )
                )

        return cards

    def _split_into_pages(self, full_text: str) -> list[str]:
        matches = list(_PAGE_MARKER_PATTERN.finditer(full_text))
        pages: list[str] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(full_text)
            )
            pages.append(full_text[start:end])
        return pages

    def _group_into_blocks(self, pages: list[str]) -> list[list[str]]:
        if not pages:
            return []
        if len(pages) <= _SPLIT_THRESHOLD_PAGES:
            return [pages]
        return [
            pages[index : index + _MAX_PAGES_PER_BLOCK]
            for index in range(0, len(pages), _MAX_PAGES_PER_BLOCK)
        ]
