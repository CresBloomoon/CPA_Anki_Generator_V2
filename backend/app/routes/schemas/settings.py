from __future__ import annotations

from pydantic import BaseModel


class AiProviderSettingsResponse(BaseModel):
    provider: str
    model_name: str


class UpdateAiProviderSettingsRequest(BaseModel):
    provider: str
    model_name: str


class AvailableModelsResponse(BaseModel):
    models: dict[str, list[str]]
