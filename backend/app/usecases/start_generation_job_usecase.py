from __future__ import annotations

import hashlib
import threading
import uuid

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import Section
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore
from app.usecases.generate_cards_for_section_usecase import (
    GenerateCardsForSectionUsecase,
)


class DuplicateGenerationJobError(Exception):
    """Raised when an identical generation request is already running.

    The idempotency key (see _build_idempotency_key) covers each selected
    section's PDF content hash, page range, deck path and title, plus the
    job's additional_prompt. A match against a job that isn't complete yet
    is very likely a double-click or an automatic retry of the same
    request (see Phase4-9's dev-log for the full incident this prevents),
    not a deliberate new one -- once the matching job completes, the same
    request is allowed again (e.g. to intentionally regenerate).
    """


class StartGenerationJobUsecase:
    def __init__(
        self,
        job_store: JobStore,
        pdf_store: PdfStore,
        generate_cards_for_section_usecase: GenerateCardsForSectionUsecase,
        max_consecutive_failures: int = 2,
    ) -> None:
        self._job_store = job_store
        self._pdf_store = pdf_store
        self._generate_cards_for_section_usecase = generate_cards_for_section_usecase
        # See B-2's dev-log: a single section failing is usually specific to
        # that section's content, not a sign the whole batch is doomed, so
        # it no longer aborts the batch by itself. Consecutive failures
        # reaching this threshold, however, are more likely a shared root
        # cause (e.g. an invalid API key) -- a safety valve against
        # repeating the same failure for every remaining section.
        self._max_consecutive_failures = max_consecutive_failures

    def execute(self, sections: list[Section], additional_prompt: str = "") -> str:
        idempotency_key = self._build_idempotency_key(sections, additional_prompt)

        existing_job = self._job_store.find_by_idempotency_key(idempotency_key)
        if existing_job is not None and not existing_job.is_complete():
            raise DuplicateGenerationJobError(
                "同じ内容のジョブが既に実行中です"
            )

        job = GenerationJob(
            job_id=str(uuid.uuid4()),
            section_jobs=[SectionJob(section=section) for section in sections],
            additional_prompt=additional_prompt,
            idempotency_key=idempotency_key,
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

    def _build_idempotency_key(
        self, sections: list[Section], additional_prompt: str
    ) -> str:
        # Sorted so two requests selecting the same sections in a
        # different order are still recognized as the same request (see
        # Phase4-9's dev-log). Note: this calls pdf_store.get_content_hash()
        # synchronously, so a section referencing a source_file that was
        # never uploaded now surfaces as PdfNotFoundError from execute()
        # itself, before any job is created.
        section_signatures = sorted(
            (
                self._pdf_store.get_content_hash(section.source_file),
                section.page_range.start_page,
                section.page_range.end_page,
                section.deck_path.joined(),
                section.title,
            )
            for section in sections
        )
        canonical = repr((additional_prompt, section_signatures))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def run(self, job: GenerationJob) -> None:
        # Counts only *consecutive* failures (reset to 0 on any success), not
        # a total failure count -- one bad section sandwiched between two
        # good ones shouldn't count against the batch (see B-2's dev-log).
        consecutive_failures = 0
        for index, section_job in enumerate(job.section_jobs):
            job.mark_running(index)
            try:
                pdf_bytes = self._pdf_store.get(section_job.section.source_file)
                cards = self._generate_cards_for_section_usecase.execute(
                    section_job.section,
                    pdf_bytes,
                    job.additional_prompt,
                    # Persist each block's cards onto the SectionJob as soon
                    # as they're generated, so a later block's failure
                    # (caught below) still leaves earlier blocks' cards in
                    # place -- see Phase4-8's dev-log.
                    on_block_generated=section_job.cards.extend,
                )
                job.mark_done(index, cards)
                consecutive_failures = 0
            except Exception as exc:  # noqa: BLE001
                job.mark_failed(index, str(exc))
                consecutive_failures += 1
                if consecutive_failures >= self._max_consecutive_failures:
                    break
