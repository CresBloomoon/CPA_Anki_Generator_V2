from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_root_path_history_repository
from app.repositories.settings.root_path_history_repository import (
    RootPathHistoryRepository,
)
from app.routes.schemas.root_path_history import (
    RootPathHistoryEntryResponse,
    RootPathHistoryResponse,
)

router = APIRouter()


@router.get("/root-path-history", response_model=RootPathHistoryResponse)
def get_root_path_history(
    repository: RootPathHistoryRepository = Depends(
        get_root_path_history_repository
    ),
) -> RootPathHistoryResponse:
    return RootPathHistoryResponse(
        entries=[
            RootPathHistoryEntryResponse(
                path=entry.path, last_used_at=entry.last_used_at
            )
            for entry in repository.load()
        ]
    )
