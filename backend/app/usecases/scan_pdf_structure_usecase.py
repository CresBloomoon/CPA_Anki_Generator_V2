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
class ScannedSection:
    # Pairs a Section with the TOC depth it was found at (see
    # section-table-indent-backend's dev-log). Kept out of Section itself:
    # Section is also built from SectionInput at generation-start time,
    # which has no notion of depth, so putting it there would leak this
    # scan-only display concern into a shared domain entity. Bundling the
    # two together (rather than two parallel lists) also rules out the two
    # ever silently drifting out of sync under future filtering/reordering.
    section: Section
    level: int


@dataclass(frozen=True)
class ScanSectionsResult:
    sections: tuple[ScannedSection, ...]
    warnings: tuple[str, ...]


class ScanPdfStructureUsecase:
    def __init__(self, pdf_structure_repository: SupportsScan) -> None:
        self._pdf_structure_repository = pdf_structure_repository

    def execute(
        self, pdf_files: list[PdfFileInput], root_path: str
    ) -> ScanSectionsResult:
        root = DeckPath.from_string(root_path)

        sections: list[ScannedSection] = []
        warnings: list[str] = []

        for pdf_file in pdf_files:
            scan_result = self._pdf_structure_repository.scan(
                pdf_file.pdf_bytes, pdf_file.source_file
            )
            warnings.extend(scan_result.warnings)
            for raw_section in scan_result.sections:
                sections.append(
                    ScannedSection(
                        section=Section(
                            title=raw_section.title,
                            page_range=raw_section.page_range,
                            deck_path=self._build_deck_path(root, raw_section),
                            source_file=raw_section.source_file,
                        ),
                        level=raw_section.level,
                    )
                )

        return ScanSectionsResult(sections=tuple(sections), warnings=tuple(warnings))

    def _build_deck_path(self, root: DeckPath, raw_section: RawSection) -> DeckPath:
        deck_path = root
        for ancestor in raw_section.ancestors:
            deck_path = deck_path.child(ancestor)
        return deck_path.child(raw_section.title)
