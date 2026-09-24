from __future__ import annotations

from abc import ABC, abstractmethod

from app.repositories.ai.dto import GenerationResult, PromptContext


class AiCardGeneratorRepository(ABC):
    @abstractmethod
    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> GenerationResult:
        raise NotImplementedError
