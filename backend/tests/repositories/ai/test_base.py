import pytest

from app.domain.card import CardContent
from app.domain.generation_job import TokenUsage
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.dto import GenerationResult, PromptContext


class TestAiCardGeneratorRepository:
    def test_cannot_be_instantiated_directly(self) -> None:
        with pytest.raises(TypeError):
            AiCardGeneratorRepository()  # type: ignore[abstract]

    def test_concrete_subclass_can_implement_generate_cards(self) -> None:
        class _FakeRepository(AiCardGeneratorRepository):
            def generate_cards(
                self, section_text: str, prompt_context: PromptContext
            ) -> GenerationResult:
                return GenerationResult(
                    card_content=CardContent(items=()),
                    token_usage=TokenUsage(0, 0),
                )

        repository = _FakeRepository()
        result = repository.generate_cards(
            "本文", PromptContext(section_title="01節")
        )
        assert result == GenerationResult(
            card_content=CardContent(items=()), token_usage=TokenUsage(0, 0)
        )
