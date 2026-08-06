from __future__ import annotations

from dataclasses import dataclass

from app.domain.section import PageRange


class PdfParsingError(Exception):
    """Raised when a PDF cannot be opened or parsed at all."""


@dataclass(frozen=True)
class RawSection:
    title: str
    ancestors: tuple[str, ...]
    level: int
    page_range: PageRange
    source_file: str


@dataclass(frozen=True)
class ScanResult:
    sections: tuple[RawSection, ...]
    warnings: tuple[str, ...] = ()
