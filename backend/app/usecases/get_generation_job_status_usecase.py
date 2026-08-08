from __future__ import annotations

from app.domain.generation_job import GenerationJob
from app.repositories.jobs.job_store import JobStore


class GetGenerationJobStatusUsecase:
    def __init__(self, job_store: JobStore) -> None:
        self._job_store = job_store

    def execute(self, job_id: str) -> GenerationJob:
        return self._job_store.get(job_id)
