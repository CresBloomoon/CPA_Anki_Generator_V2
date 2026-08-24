from __future__ import annotations

import logging
import re
import time
from typing import Callable, Protocol

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

logger = logging.getLogger(__name__)


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

    def execute(
        self,
        section: Section,
        pdf_bytes: bytes,
        additional_prompt: str = "",
        on_block_generated: Callable[[list[Card]], None] | None = None,
    ) -> list[Card]:
        # on_block_generated, if given, is called once per block with just
        # that block's cards (not the running total) immediately after the
        # block succeeds. This lets the caller (StartGenerationJobUsecase)
        # persist progress incrementally onto the SectionJob it owns, so a
        # later block's failure doesn't discard already-paid-for,
        # already-generated cards from earlier blocks -- see Phase4-8's
        # dev-log for the full incident this addresses.
        full_text = self._pdf_structure_repository.extract_text_from_range(
            pdf_bytes, section.page_range.start_page, section.page_range.end_page
        )
        blocks = self._group_into_blocks(self._split_into_pages(full_text))
        total_blocks = len(blocks)

        cards: list[Card] = []
        for position, block_pages in enumerate(blocks, start=1):
            prompt_context = PromptContext(
                section_title=section.title,
                additional_prompt=additional_prompt,
                block_index=position if total_blocks > 1 else None,
                block_count=total_blocks if total_blocks > 1 else None,
            )
            logger.info(
                "[%s] ブロック %d/%d 処理開始", section.title, position, total_blocks
            )
            started_at = time.monotonic()
            # Any failure here (AI error, unrecoverable JSON, ...) is
            # intentionally left to propagate -- deciding whether to abort
            # the rest of the job or keep sections already completed is
            # Phase3-3's job, not this usecase's.
            card_content = self._ai_repository.generate_cards(
                "".join(block_pages), prompt_context
            )
            elapsed_seconds = time.monotonic() - started_at
            logger.info(
                "[%s] ブロック %d/%d 完了、%d件生成（%.1f秒）",
                section.title,
                position,
                total_blocks,
                len(card_content.items),
                elapsed_seconds,
            )
            block_cards = [
                Card(
                    content=item,
                    section_title=section.title,
                    deck_path=section.deck_path,
                )
                for item in card_content.items
            ]
            cards.extend(block_cards)
            if on_block_generated is not None:
                on_block_generated(block_cards)

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
