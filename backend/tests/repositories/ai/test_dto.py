import pytest

from app.repositories.ai.dto import PromptContext


class TestPromptContext:
    def test_empty_section_title_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="")

    def test_block_index_without_block_count_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="01節", block_index=1)

    def test_block_count_without_block_index_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="01節", block_count=3)

    def test_block_index_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="01節", block_index=0, block_count=3)

    def test_block_index_above_block_count_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="01節", block_index=4, block_count=3)

    def test_block_count_below_one_raises(self) -> None:
        with pytest.raises(ValueError):
            PromptContext(section_title="01節", block_index=1, block_count=0)

    def test_valid_block_fields_construct(self) -> None:
        context = PromptContext(section_title="01節", block_index=2, block_count=3)
        assert context.block_index == 2
        assert context.block_count == 3

    def test_block_fields_default_to_none(self) -> None:
        context = PromptContext(section_title="01節")
        assert context.block_index is None
        assert context.block_count is None
