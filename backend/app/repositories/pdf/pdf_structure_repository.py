from __future__ import annotations

import re
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.domain.section import PageRange
from app.repositories.pdf.dto import PdfParsingError, RawSection, ScanResult

_ZENKAKU_DIGITS = "０１２３４５６７８９"
_HANKAKU_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(_ZENKAKU_DIGITS, _HANKAKU_DIGITS)

# Matches a leading "第N<unit>" prefix so its number can be zero-padded for
# consistent alphabetical sorting (e.g. so "第2章" sorts before "第10章" in
# Anki's deck browser). Titles that don't start with this pattern (目次,
# ＜はじめに＞, 序章, 補章, kanji-numeral headings, ...) are passed through
# unchanged rather than forced into a shape they don't have.
_LEADING_NUMBERED_PREFIX = re.compile(r"^第(\d+)([部編章節項款])(.*)$")


def _normalize_digits(text: str) -> str:
    return text.translate(_DIGIT_TRANSLATION)


def _normalize_title(raw_title: str) -> str:
    normalized = _normalize_digits(raw_title.strip())
    match = _LEADING_NUMBERED_PREFIX.match(normalized)
    if not match:
        return normalized
    number, unit, rest = match.groups()
    return f"第{int(number):02d}{unit}{rest}"


@dataclass
class _PendingSection:
    title: str
    ancestors: tuple[str, ...]
    level: int
    start_page: int


class PdfStructureRepository:
    def scan(self, pdf_bytes: bytes, source_file: str) -> ScanResult:
        doc = self._open(pdf_bytes)
        try:
            warnings: list[str] = []
            sections = self._build_sections_from_toc(doc)
            if not sections:
                # A silent {"sections": [], "warnings": []} reads as "the
                # button did nothing" from the UI. Naming the file makes it
                # clear this is TOC-only detection (ADR 0001) working as
                # designed, not a bug -- especially with multiple PDFs
                # scanned together, where only some might lack a TOC.
                warnings.append(f"{source_file} にはTOC（しおり）が見つかりませんでした")
            raw_sections = self._finalize(sections, source_file, warnings)
            return ScanResult(sections=tuple(raw_sections), warnings=tuple(warnings))
        finally:
            doc.close()

    def extract_text_from_range(
        self, pdf_bytes: bytes, start_page: int, end_page: int | None = None
    ) -> str:
        doc = self._open(pdf_bytes)
        try:
            return self._extract_text(doc, start_page, end_page)
        finally:
            doc.close()

    def _open(self, pdf_bytes: bytes) -> fitz.Document:
        try:
            return fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PdfParsingError(f"failed to open PDF: {exc}") from exc

    def _extract_text(
        self, doc: fitz.Document, start_page: int, end_page: int | None
    ) -> str:
        total_pages = doc.page_count
        actual_start = max(0, start_page - 1)
        actual_end = end_page - 1 if end_page else total_pages
        chunks: list[str] = []
        for index in range(actual_start, min(actual_end, total_pages)):
            chunks.append(f"\n--- ページ {index + 1} ---\n{doc[index].get_text()}\n")
        return "".join(chunks).strip()

    def _build_sections_from_toc(self, doc: fitz.Document) -> list[_PendingSection]:
        # doc.get_toc() returns a flat (level, title, page) list in document
        # order. The hierarchy depth varies by subject (some textbooks have
        # no sub-levels at all, others have two or more), so instead of
        # assuming a fixed "chapter -> section" shape, we track whichever
        # title was most recently seen at each level and use that to build
        # each entry's ancestor breadcrumb.
        ancestors_by_level: dict[int, str] = {}
        sections: list[_PendingSection] = []

        for level, raw_title, page_number in doc.get_toc():
            for deeper_level in [lv for lv in ancestors_by_level if lv >= level]:
                del ancestors_by_level[deeper_level]

            ancestors = tuple(
                ancestors_by_level[lv] for lv in sorted(ancestors_by_level)
            )
            title = _normalize_title(raw_title)
            ancestors_by_level[level] = title

            # Every TOC entry becomes a section candidate — noise entries
            # (目次, はじめに, ...) and duplicate titles under different
            # parents are left in for the user to review/deselect in the
            # table, rather than guessed away here.
            sections.append(
                _PendingSection(
                    title=title,
                    ancestors=ancestors,
                    level=level,
                    start_page=page_number,
                )
            )

        return sections

    def _finalize(
        self,
        sections: list[_PendingSection],
        source_file: str,
        warnings: list[str],
    ) -> list[RawSection]:
        raw_sections: list[RawSection] = []
        for position, pending in enumerate(sections):
            end_page = (
                sections[position + 1].start_page
                if position + 1 < len(sections)
                else None
            )
            if end_page is not None and end_page < pending.start_page:
                warnings.append(
                    f"section {pending.title!r} has a start_page "
                    f"({pending.start_page}) after the next TOC entry's page "
                    f"({end_page}); leaving its end page open-ended"
                )
                end_page = None

            raw_sections.append(
                RawSection(
                    title=pending.title,
                    ancestors=pending.ancestors,
                    level=pending.level,
                    page_range=PageRange(
                        start_page=pending.start_page, end_page=end_page
                    ),
                    source_file=source_file,
                )
            )
        return raw_sections
