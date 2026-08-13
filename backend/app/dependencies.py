from __future__ import annotations

from fastapi import HTTPException

from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.factory import (
    AiCardGeneratorFactory,
    MissingApiKeyError,
    UnsupportedProviderError,
)
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore
from app.repositories.settings.settings_repository import (
    AiProviderSettings,
    SettingsRepository,
)

# Process-wide singletons. No persistence: state is lost on backend
# restart, which is an accepted trade-off for a single-user, Docker
# Compose-only deployment (see JobStore/PdfStore docstrings).
pdf_store = PdfStore()
job_store = JobStore()


def get_pdf_store() -> PdfStore:
    return pdf_store


def get_job_store() -> JobStore:
    return job_store


def _build_ai_repository(settings: AiProviderSettings) -> AiCardGeneratorRepository:
    # Split out from get_ai_card_generator_repository() so this
    # settings->repository->HTTP-error mapping can be unit tested directly,
    # without going through FastAPI's dependency resolution or touching the
    # real settings.json file on disk.
    try:
        return AiCardGeneratorFactory().create(settings)
    except (MissingApiKeyError, UnsupportedProviderError) as exc:
        # Not the caller's fault -- the server is misconfigured (missing
        # .env key, or an unsupported provider in settings.json) -- so this
        # is a 500, not a 4xx.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_ai_card_generator_repository() -> AiCardGeneratorRepository:
    # Settings are re-read from settings.json on every call (no caching),
    # so a provider/model change made via the future settings API takes
    # effect on the next generation job without a backend restart.
    settings = SettingsRepository().load()
    return _build_ai_repository(settings)
