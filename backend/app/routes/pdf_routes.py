from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.dependencies import get_pdf_store, get_root_path_history_repository
from app.domain.section import DeckPath
from app.repositories.pdf.dto import PdfParsingError
from app.repositories.pdf.pdf_store import PdfNotFoundError, PdfStore
from app.repositories.pdf.pdf_structure_repository import PdfStructureRepository
from app.repositories.settings.root_path_history_repository import (
    RootPathHistoryRepository,
)
from app.routes.page_range_display import to_display_end_page
from app.routes.schemas.pdf import (
    ScanRequest,
    ScanResponse,
    SectionScanResult,
    UploadPdfResponse,
)
from app.usecases.scan_pdf_structure_usecase import (
    PdfFileInput,
    ScanPdfStructureUsecase,
)

router = APIRouter()


@router.post("/pdfs", response_model=UploadPdfResponse)
async def upload_pdf(
    file: UploadFile, pdf_store: PdfStore = Depends(get_pdf_store)
) -> UploadPdfResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    pdf_bytes = await file.read()
    pdf_store.save(file.filename, pdf_bytes)

    return UploadPdfResponse(source_file=file.filename, size_bytes=len(pdf_bytes))


@router.post("/scan", response_model=ScanResponse)
def scan_pdfs(
    request: ScanRequest,
    pdf_store: PdfStore = Depends(get_pdf_store),
    root_path_history_repository: RootPathHistoryRepository = Depends(
        get_root_path_history_repository
    ),
) -> ScanResponse:
    try:
        pdf_files = [
            PdfFileInput(
                pdf_bytes=pdf_store.get(source_file), source_file=source_file
            )
            for source_file in request.source_files
        ]
    except PdfNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    usecase = ScanPdfStructureUsecase(PdfStructureRepository())
    try:
        result = usecase.execute(pdf_files, request.root_path)
    except PdfParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        # e.g. DeckPath.from_string(root_path) rejecting a root_path that's
        # empty (or entirely whitespace/"::") even after normalization.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Recorded as the normalized/canonical form (not request.root_path
    # verbatim) so history entries never carry the trailing/doubled "::"
    # or stray whitespace that from_string() already strips elsewhere.
    root_path_history_repository.add_or_update(
        DeckPath.from_string(request.root_path).joined()
    )

    return ScanResponse(
        sections=[
            SectionScanResult(
                title=section.title,
                start_page=section.page_range.start_page,
                end_page=to_display_end_page(section.page_range.end_page),
                deck_path=section.deck_path.joined(),
                source_file=section.source_file,
            )
            for section in result.sections
        ],
        warnings=list(result.warnings),
    )
