from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.section import DeckPath, Section
from app.repositories.pdf.dto import RawSection, ScanResult


class SupportsScan(Protocol):
    """What this usecase needs from a PDF structure repository.

    Defined as a structural Protocol (rather than importing the concrete
    PdfStructureRepository class) so this module -- and anything that tests
    it -- has no dependency on PyMuPDF.
    """

    def scan(self, pdf_bytes: bytes, source_file: str) -> ScanResult: ...


@dataclass(frozen=True)
class PdfFileInput:
    pdf_bytes: bytes
    source_file: str


@dataclass(frozen=True)
class ScanSectionsResult:
    sections: tuple[Section, ...]
    warnings: tuple[str, ...]


class ScanPdfStructureUsecase:
    def __init__(self, pdf_structure_repository: SupportsScan) -> None:
        self._pdf_structure_repository = pdf_structure_repository

    def execute(
        self, pdf_files: list[PdfFileInput], root_path: str
    ) -> ScanSectionsResult:
        root = DeckPath.from_string(root_path)

        sections: list[Section] = []
        warnings: list[str] = []

        for pdf_file in pdf_files:
            scan_result = self._pdf_structure_repository.scan(
                pdf_file.pdf_bytes, pdf_file.source_file
            )
            warnings.extend(scan_result.warnings)
            for raw_section in scan_result.sections:
                sections.append(
                    Section(
                        title=raw_section.title,
                        page_range=raw_section.page_range,
                        deck_path=self._build_deck_path(root, raw_section),
                        source_file=raw_section.source_file,
                    )
                )

        return ScanSectionsResult(sections=tuple(sections), warnings=tuple(warnings))

    def _build_deck_path(self, root: DeckPath, raw_section: RawSection) -> DeckPath:
        deck_path = root
        for ancestor in raw_section.ancestors:
            deck_path = deck_path.child(ancestor)
        return deck_path.child(raw_section.title)
