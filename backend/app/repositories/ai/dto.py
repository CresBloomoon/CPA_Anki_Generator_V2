from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptContext:
    section_title: str
    additional_prompt: str = ""
