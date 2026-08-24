import pytest

from app.domain.card import CardContent, CardContentItem
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.dto import PromptContext
from app.usecases.generate_cards_for_section_usecase import (
    GenerateCardsForSectionUsecase,
)


def _build_marked_text(num_pages: int) -> str:
    return "".join(
        f"\n--- ページ {page} ---\npage {page} content\n"
        for page in range(1, num_pages + 1)
    )


class _FakePdfStructureRepository:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text_from_range(
        self, pdf_bytes: bytes, start_page: int, end_page: int | None = None
    ) -> str:
        return self._text


class _FakeAiRepository(AiCardGeneratorRepository):
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, PromptContext]] = []
        self._error = error

    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> CardContent:
        self.calls.append((section_text, prompt_context))
        if self._error is not None:
            raise self._error
        item = CardContentItem(
            title=f"card-{len(self.calls)}",
            question="Q",
            ronsho_body="R",
            kaisetsu_body="K",
            yo_suruni_body="Y",
            ryui_body="特になし",
            rank_tanto="A",
            rank_ronbun="B",
            page_code="1-1-1",
        )
        return CardContent(items=(item,))


def _make_section(
    start_page: int = 1, end_page: int | None = None, title: str = "01節 X"
) -> Section:
    return Section(
        title=title,
        page_range=PageRange(start_page=start_page, end_page=end_page),
        deck_path=DeckPath.from_string("Root::A"),
        source_file="book.pdf",
    )


class TestGenerateCardsForSectionUsecase:
    @pytest.mark.parametrize("page_count", [1, 5])
    def test_single_block_when_page_count_at_or_below_threshold(
        self, page_count: int
    ) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(page_count))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        cards = usecase.execute(_make_section(), pdf_bytes=b"...")

        assert len(ai_repo.calls) == 1
        _, context = ai_repo.calls[0]
        assert context.block_index is None
        assert context.block_count is None
        assert len(cards) == 1

    def test_splits_into_four_page_blocks_when_more_than_five_pages(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(6))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        usecase.execute(_make_section(), pdf_bytes=b"...")

        assert len(ai_repo.calls) == 2
        first_text, first_context = ai_repo.calls[0]
        second_text, second_context = ai_repo.calls[1]

        assert first_context.block_index == 1
        assert first_context.block_count == 2
        assert second_context.block_index == 2
        assert second_context.block_count == 2

        # First block covers pages 1-4, second block covers the remaining
        # pages 5-6 (last block gets the remainder).
        for page in (1, 2, 3, 4):
            assert f"--- ページ {page} ---" in first_text
        assert "--- ページ 5 ---" not in first_text
        for page in (5, 6):
            assert f"--- ページ {page} ---" in second_text

    def test_cards_are_stamped_with_section_title_and_deck_path(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(1))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)
        section = _make_section(title="01節 会計の意義")

        cards = usecase.execute(section, pdf_bytes=b"...")

        assert cards[0].section_title == "01節 会計の意義"
        assert cards[0].deck_path == section.deck_path

    def test_ai_repository_failure_propagates_without_being_swallowed(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(1))
        ai_repo = _FakeAiRepository(error=RuntimeError("boom"))
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        with pytest.raises(RuntimeError, match="boom"):
            usecase.execute(_make_section(), pdf_bytes=b"...")

    def test_empty_extracted_text_produces_no_cards_and_no_ai_calls(self) -> None:
        # Corresponds to a zero-length page range (start_page == end_page),
        # which is a legitimate case per ADR 0001 (e.g. a part heading that
        # shares its start page with the next TOC entry).
        pdf_repo = _FakePdfStructureRepository("")
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        cards = usecase.execute(_make_section(), pdf_bytes=b"...")

        assert cards == []
        assert ai_repo.calls == []

    def test_additional_prompt_is_passed_through_to_prompt_context(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(1))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        usecase.execute(
            _make_section(), pdf_bytes=b"...", additional_prompt="具体例を厚めに"
        )

        _, context = ai_repo.calls[0]
        assert context.additional_prompt == "具体例を厚めに"

    def test_additional_prompt_defaults_to_empty_string(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(1))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        usecase.execute(_make_section(), pdf_bytes=b"...")

        _, context = ai_repo.calls[0]
        assert context.additional_prompt == ""

    def test_open_ended_page_range_is_passed_through_to_extraction(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(2))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)
        section = _make_section(start_page=10, end_page=None)

        cards = usecase.execute(section, pdf_bytes=b"...")

        assert len(cards) == 1


class TestOnBlockGeneratedCallback:
    def test_called_once_per_block_with_only_that_blocks_cards(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(6))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)
        reported_blocks: list[list] = []

        cards = usecase.execute(
            _make_section(),
            pdf_bytes=b"...",
            on_block_generated=reported_blocks.append,
        )

        # 6 pages -> split into 2 blocks (see
        # test_splits_into_four_page_blocks_when_more_than_five_pages).
        assert len(reported_blocks) == 2
        assert len(reported_blocks[0]) == 1
        assert len(reported_blocks[1]) == 1
        assert reported_blocks[0] + reported_blocks[1] == cards

    def test_earlier_blocks_are_reported_before_a_later_block_fails(self) -> None:
        # Reproduces the incident this callback exists to prevent: block 2
        # of 2 fails after block 1 already succeeded. The callback must
        # still have been called for block 1's cards before the exception
        # propagates, so the caller can keep them.
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(6))
        ai_repo = _FakeAiRepository()

        call_count = 0
        original_generate_cards = ai_repo.generate_cards

        def flaky_generate_cards(section_text, prompt_context):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("2ブロック目で失敗")
            return original_generate_cards(section_text, prompt_context)

        ai_repo.generate_cards = flaky_generate_cards
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)
        reported_blocks: list[list] = []

        with pytest.raises(RuntimeError, match="2ブロック目で失敗"):
            usecase.execute(
                _make_section(),
                pdf_bytes=b"...",
                on_block_generated=reported_blocks.append,
            )

        assert len(reported_blocks) == 1
        assert len(reported_blocks[0]) == 1

    def test_defaults_to_none_and_does_not_require_a_callback(self) -> None:
        pdf_repo = _FakePdfStructureRepository(_build_marked_text(1))
        ai_repo = _FakeAiRepository()
        usecase = GenerateCardsForSectionUsecase(pdf_repo, ai_repo)

        cards = usecase.execute(_make_section(), pdf_bytes=b"...")

        assert len(cards) == 1
