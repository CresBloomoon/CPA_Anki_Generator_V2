from __future__ import annotations

import threading
import uuid

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import Section
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore
from app.usecases.generate_cards_for_section_usecase import (
    GenerateCardsForSectionUsecase,
)


class StartGenerationJobUsecase:
    def __init__(
        self,
        job_store: JobStore,
        pdf_store: PdfStore,
        generate_cards_for_section_usecase: GenerateCardsForSectionUsecase,
    ) -> None:
        self._job_store = job_store
        self._pdf_store = pdf_store
        self._generate_cards_for_section_usecase = generate_cards_for_section_usecase

    def execute(self, sections: list[Section]) -> str:
        job = GenerationJob(
            job_id=str(uuid.uuid4()),
            section_jobs=[SectionJob(section=section) for section in sections],
        )
        self._job_store.save(job)

        # Deliberately a plain background thread rather than FastAPI's
        # BackgroundTasks: GeminiRepository.generate_cards is fully
        # synchronous (blocking time.sleep() retries), so this usecase
        # manages its own backgrounding and stays framework-agnostic. The
        # route layer just calls execute() and gets a job_id back
        # immediately.
        threading.Thread(target=self.run, args=(job,), daemon=True).start()

        return job.job_id

    def run(self, job: GenerationJob) -> None:
        for index, section_job in enumerate(job.section_jobs):
            job.mark_running(index)
            try:
                pdf_bytes = self._pdf_store.get(section_job.section.source_file)
                cards = self._generate_cards_for_section_usecase.execute(
                    section_job.section, pdf_bytes
                )
                job.mark_done(index, cards)
            except Exception as exc:  # noqa: BLE001 - any failure aborts the batch
                job.mark_failed(index, str(exc))
                break
