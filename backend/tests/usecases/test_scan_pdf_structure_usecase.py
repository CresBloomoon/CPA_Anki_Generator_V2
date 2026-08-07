from app.domain.section import PageRange
from app.repositories.pdf.dto import RawSection, ScanResult
from app.usecases.scan_pdf_structure_usecase import (
    PdfFileInput,
    ScanPdfStructureUsecase,
)


class _FakePdfStructureRepository:
    def __init__(self, results_by_source_file: dict[str, ScanResult]) -> None:
        self._results_by_source_file = results_by_source_file

    def scan(self, pdf_bytes: bytes, source_file: str) -> ScanResult:
        return self._results_by_source_file[source_file]


def _raw_section(
    title: str,
    ancestors: tuple[str, ...] = (),
    level: int = 1,
    start_page: int = 1,
    end_page: int | None = None,
    source_file: str = "book.pdf",
) -> RawSection:
    return RawSection(
        title=title,
        ancestors=ancestors,
        level=level,
        page_range=PageRange(start_page=start_page, end_page=end_page),
        source_file=source_file,
    )


class TestScanPdfStructureUsecase:
    def test_flat_hierarchy_deck_path_is_root_joined_with_title(self) -> None:
        repository = _FakePdfStructureRepository(
            {"book.pdf": ScanResult(sections=(_raw_section("第01章 総論"),))}
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [PdfFileInput(pdf_bytes=b"...", source_file="book.pdf")],
            root_path="公認会計士試験::管理会計論",
        )

        assert len(result.sections) == 1
        assert (
            result.sections[0].deck_path.joined()
            == "公認会計士試験::管理会計論::第01章 総論"
        )

    def test_ancestors_are_inserted_between_root_and_title(self) -> None:
        # Mirrors the 財務会計論-style 部->章 hierarchy: ancestors chain
        # between root_path and the section's own title.
        repository = _FakePdfStructureRepository(
            {
                "book.pdf": ScanResult(
                    sections=(
                        _raw_section(
                            "第01章 財務会計の基礎概念",
                            ancestors=("第01部 コンプリートチェック",),
                        ),
                    )
                )
            }
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [PdfFileInput(pdf_bytes=b"...", source_file="book.pdf")],
            root_path="公認会計士試験::財務会計論",
        )

        assert (
            result.sections[0].deck_path.joined()
            == "公認会計士試験::財務会計論::第01部 コンプリートチェック::第01章 財務会計の基礎概念"
        )

    def test_multiple_ancestor_levels_are_all_inserted_in_order(self) -> None:
        repository = _FakePdfStructureRepository(
            {
                "book.pdf": ScanResult(
                    sections=(
                        _raw_section(
                            "第01節 詳細",
                            ancestors=("第01部 A", "第01章 B"),
                        ),
                    )
                )
            }
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [PdfFileInput(pdf_bytes=b"...", source_file="book.pdf")],
            root_path="Root",
        )

        assert result.sections[0].deck_path.joined() == "Root::第01部 A::第01章 B::第01節 詳細"

    def test_source_file_is_preserved_on_each_section(self) -> None:
        repository = _FakePdfStructureRepository(
            {"book.pdf": ScanResult(sections=(_raw_section("t", source_file="book.pdf"),))}
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [PdfFileInput(pdf_bytes=b"...", source_file="book.pdf")],
            root_path="Root",
        )

        assert result.sections[0].source_file == "book.pdf"

    def test_multiple_pdfs_are_scanned_and_aggregated_into_one_flat_list(self) -> None:
        repository = _FakePdfStructureRepository(
            {
                "book1.pdf": ScanResult(
                    sections=(_raw_section("t1", source_file="book1.pdf"),)
                ),
                "book2.pdf": ScanResult(
                    sections=(_raw_section("t2", source_file="book2.pdf"),)
                ),
            }
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [
                PdfFileInput(pdf_bytes=b"...", source_file="book1.pdf"),
                PdfFileInput(pdf_bytes=b"...", source_file="book2.pdf"),
            ],
            root_path="Root",
        )

        assert len(result.sections) == 2
        assert {s.source_file for s in result.sections} == {"book1.pdf", "book2.pdf"}

    def test_warnings_from_all_files_are_aggregated(self) -> None:
        repository = _FakePdfStructureRepository(
            {
                "book1.pdf": ScanResult(
                    sections=(_raw_section("t1"),), warnings=("w1",)
                ),
                "book2.pdf": ScanResult(
                    sections=(_raw_section("t2"),), warnings=("w2", "w3")
                ),
            }
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [
                PdfFileInput(pdf_bytes=b"...", source_file="book1.pdf"),
                PdfFileInput(pdf_bytes=b"...", source_file="book2.pdf"),
            ],
            root_path="Root",
        )

        assert result.warnings == ("w1", "w2", "w3")

    def test_page_range_is_carried_through_unchanged(self) -> None:
        repository = _FakePdfStructureRepository(
            {
                "book.pdf": ScanResult(
                    sections=(_raw_section("t", start_page=5, end_page=10),)
                )
            }
        )
        usecase = ScanPdfStructureUsecase(repository)

        result = usecase.execute(
            [PdfFileInput(pdf_bytes=b"...", source_file="book.pdf")],
            root_path="Root",
        )

        assert result.sections[0].page_range.start_page == 5
        assert result.sections[0].page_range.end_page == 10
