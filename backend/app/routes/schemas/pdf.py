from __future__ import annotations

from pydantic import BaseModel


class UploadPdfResponse(BaseModel):
    source_file: str
    size_bytes: int


class ScanRequest(BaseModel):
    source_files: list[str]
    root_path: str


class SectionScanResult(BaseModel):
    title: str
    start_page: int
    end_page: int | None
    deck_path: str
    source_file: str
    # TOC depth at scan time (see section-table-indent-backend's dev-log).
    # Purely for frontend display (indentation) -- not used by generation.
    level: int


class ScanResponse(BaseModel):
    sections: list[SectionScanResult]
    warnings: list[str]
