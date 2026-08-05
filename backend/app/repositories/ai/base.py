from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.card import CardContent
from app.repositories.ai.dto import PromptContext


class AiCardGeneratorRepository(ABC):
    @abstractmethod
    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> CardContent:
        raise NotImplementedError
