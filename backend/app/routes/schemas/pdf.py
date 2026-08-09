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


class ScanResponse(BaseModel):
    sections: list[SectionScanResult]
    warnings: list[str]
