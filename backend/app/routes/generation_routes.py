from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.dependencies import get_ai_card_generator_repository, get_job_store, get_pdf_store
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.anki.anki_package_repository import AnkiPackageRepository
from app.repositories.jobs.job_store import JobNotFoundError, JobStore
from app.repositories.pdf.pdf_store import PdfNotFoundError, PdfStore
from app.repositories.pdf.pdf_structure_repository import PdfStructureRepository
from app.routes.page_range_display import to_internal_end_page
from app.routes.schemas.generation import (
    GenerationJobStatusResponse,
    SectionJobStatusResponse,
    StartGenerationJobResponse,
    StartGenerationRequest,
)
from app.usecases.build_anki_package_usecase import BuildAnkiPackageUsecase
from app.usecases.generate_cards_for_section_usecase import (
    GenerateCardsForSectionUsecase,
)
from app.usecases.get_generation_job_status_usecase import (
    GetGenerationJobStatusUsecase,
)
from app.usecases.start_generation_job_usecase import (
    DuplicateGenerationJobError,
    StartGenerationJobUsecase,
)

router = APIRouter()


@router.post("/generation-jobs", response_model=StartGenerationJobResponse)
def start_generation_job(
    request: StartGenerationRequest,
    job_store: JobStore = Depends(get_job_store),
    pdf_store: PdfStore = Depends(get_pdf_store),
    ai_repository: AiCardGeneratorRepository = Depends(
        get_ai_card_generator_repository
    ),
) -> StartGenerationJobResponse:
    try:
        sections = [
            Section(
                title=section_input.title,
                page_range=PageRange(
                    start_page=section_input.start_page,
                    end_page=to_internal_end_page(section_input.end_page),
                ),
                deck_path=DeckPath.from_string(section_input.deck_path),
                source_file=section_input.source_file,
            )
            for section_input in request.sections
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    generate_cards_usecase = GenerateCardsForSectionUsecase(
        PdfStructureRepository(), ai_repository
    )
    usecase = StartGenerationJobUsecase(job_store, pdf_store, generate_cards_usecase)
    try:
        job_id = usecase.execute(sections, request.additional_prompt)
    except PdfNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateGenerationJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StartGenerationJobResponse(job_id=job_id)


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobStatusResponse)
def get_generation_job_status(
    job_id: str, job_store: JobStore = Depends(get_job_store)
) -> GenerationJobStatusResponse:
    usecase = GetGenerationJobStatusUsecase(job_store)
    try:
        job = usecase.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return GenerationJobStatusResponse(
        job_id=job.job_id,
        is_complete=job.is_complete(),
        section_jobs=[
            SectionJobStatusResponse(
                title=section_job.section.title,
                status=section_job.status.name,
                card_count=len(section_job.cards),
                error_message=section_job.error_message,
            )
            for section_job in job.section_jobs
        ],
    )


@router.get("/generation-jobs/{job_id}/download")
def download_generation_job_package(
    job_id: str, job_store: JobStore = Depends(get_job_store)
) -> Response:
    status_usecase = GetGenerationJobStatusUsecase(job_store)
    try:
        job = status_usecase.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    build_usecase = BuildAnkiPackageUsecase(AnkiPackageRepository())
    result = build_usecase.execute(job)

    filename = "generated.apkg" if result.is_complete else "generated_partial.apkg"
    return Response(
        content=result.apkg_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
