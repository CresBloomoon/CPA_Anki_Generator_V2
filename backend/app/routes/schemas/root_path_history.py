from __future__ import annotations

from pydantic import BaseModel


class RootPathHistoryEntryResponse(BaseModel):
    path: str
    last_used_at: str


class RootPathHistoryResponse(BaseModel):
    entries: list[RootPathHistoryEntryResponse]
