from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from app.dependencies import get_ai_card_generator_repository, get_job_store, get_pdf_store
from app.domain.generation_job import SectionJobStatus
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.anki.anki_package_repository import AnkiPackageRepository
from app.repositories.jobs.job_store import JobNotFoundError, JobStore
from app.repositories.pdf.pdf_store import PdfNotFoundError, PdfStore
from app.repositories.pdf.pdf_structure_repository import PdfStructureRepository
from app.routes.page_range_display import to_internal_end_page
from app.routes.schemas.generation import (
    GenerationJobListResponse,
    GenerationJobStatusResponse,
    GenerationJobSummaryResponse,
    SectionJobStatusResponse,
    StartGenerationJobResponse,
    StartGenerationRequest,
)
from app.usecases.build_anki_package_usecase import (
    AnkiPackageResult,
    BuildAnkiPackageUsecase,
    SectionIndexNotFoundError,
    SectionNotDownloadableError,
)
from app.usecases.generate_cards_for_section_usecase import (
    GenerateCardsForSectionUsecase,
)
from app.usecases.get_generation_job_status_usecase import (
    GetGenerationJobStatusUsecase,
)
from app.usecases.list_generation_jobs_usecase import ListGenerationJobsUsecase
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
        job_id = usecase.execute(sections, request.additional_prompt, request.root_path)
    except PdfNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateGenerationJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StartGenerationJobResponse(job_id=job_id)


@router.get("/generation-jobs", response_model=GenerationJobListResponse)
def list_generation_jobs(
    job_store: JobStore = Depends(get_job_store),
) -> GenerationJobListResponse:
    usecase = ListGenerationJobsUsecase(job_store)
    jobs = usecase.execute()

    return GenerationJobListResponse(
        jobs=[
            GenerationJobSummaryResponse(
                job_id=job.job_id,
                root_path=job.root_path,
                created_at=job.created_at,
                is_complete=job.is_complete(),
                section_count=len(job.section_jobs),
                done_section_count=sum(
                    1
                    for section_job in job.section_jobs
                    if section_job.status
                    in (SectionJobStatus.DONE, SectionJobStatus.PARTIALLY_DONE)
                ),
            )
            for job in jobs
        ]
    )


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
                elapsed_seconds=section_job.elapsed_seconds(),
            )
            for section_job in job.section_jobs
        ],
    )


_FILENAME_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')


def _sanitize_filename_component(name: str) -> str:
    return _FILENAME_UNSAFE_CHARS.sub("_", name)


def _build_apkg_response(
    result: AnkiPackageResult,
    complete_filename: str,
    partial_filename: str,
    display_name: str | None = None,
) -> Response:
    ascii_filename = complete_filename if result.is_complete else partial_filename
    disposition = f'attachment; filename="{ascii_filename}"'

    if display_name is not None:
        # display_name is a human-readable name (e.g. a section title) that
        # may contain non-ASCII characters and/or characters unsafe in a
        # filename -- RFC 5987's filename* carries it for modern clients,
        # while filename= above stays as the ASCII-safe fallback for
        # anything that doesn't understand filename* (see Phase4-10's
        # dev-log).
        suffix = "" if result.is_complete else "（一部完了）"
        readable_name = _sanitize_filename_component(f"{display_name}{suffix}") + ".apkg"
        disposition += f"; filename*=UTF-8''{quote(readable_name, safe='')}"

    return Response(
        content=result.apkg_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": disposition},
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

    return _build_apkg_response(result, "generated.apkg", "generated_partial.apkg")


@router.get("/generation-jobs/{job_id}/sections/{section_index}/download")
def download_generation_job_section_package(
    job_id: str, section_index: int, job_store: JobStore = Depends(get_job_store)
) -> Response:
    status_usecase = GetGenerationJobStatusUsecase(job_store)
    try:
        job = status_usecase.execute(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    build_usecase = BuildAnkiPackageUsecase(AnkiPackageRepository())
    try:
        result = build_usecase.execute_for_section(job, section_index)
    except SectionIndexNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SectionNotDownloadableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    section_title = job.section_jobs[section_index].section.title
    return _build_apkg_response(
        result,
        "generated_section.apkg",
        "generated_section_partial.apkg",
        display_name=section_title,
    )
