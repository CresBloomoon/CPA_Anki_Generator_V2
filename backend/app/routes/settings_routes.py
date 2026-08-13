from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_settings_repository
from app.repositories.settings.settings_repository import (
    AiProviderSettings,
    SettingsRepository,
)
from app.routes.schemas.settings import (
    AiProviderSettingsResponse,
    UpdateAiProviderSettingsRequest,
)

router = APIRouter()


@router.get("/settings", response_model=AiProviderSettingsResponse)
def get_settings(
    settings_repository: SettingsRepository = Depends(get_settings_repository),
) -> AiProviderSettingsResponse:
    settings = settings_repository.load()
    return AiProviderSettingsResponse(
        provider=settings.provider, model_name=settings.model_name
    )


@router.put("/settings", response_model=AiProviderSettingsResponse)
def update_settings(
    request: UpdateAiProviderSettingsRequest,
    settings_repository: SettingsRepository = Depends(get_settings_repository),
) -> AiProviderSettingsResponse:
    try:
        settings = AiProviderSettings(
            provider=request.provider, model_name=request.model_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    settings_repository.save(settings)

    return AiProviderSettingsResponse(
        provider=settings.provider, model_name=settings.model_name
    )
