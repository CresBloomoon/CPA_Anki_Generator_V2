from __future__ import annotations

from pydantic import BaseModel, Field


class SectionInput(BaseModel):
    title: str
    start_page: int = Field(ge=1)
    end_page: int | None = None
    deck_path: str
    source_file: str


class StartGenerationRequest(BaseModel):
    sections: list[SectionInput]
    additional_prompt: str = ""
