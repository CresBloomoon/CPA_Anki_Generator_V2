from __future__ import annotations

from app.domain.generation_job import GenerationJob
from app.repositories.jobs.job_store import JobStore


class ListGenerationJobsUsecase:
    def __init__(self, job_store: JobStore) -> None:
        self._job_store = job_store

    def execute(self) -> list[GenerationJob]:
        # Newest-first: JobStore/GenerationJobRepository intentionally
        # don't order their results (see Phase7-2-4's dev-log), so
        # deciding the display order belongs here.
        return sorted(
            self._job_store.list_all(), key=lambda job: job.created_at, reverse=True
        )
