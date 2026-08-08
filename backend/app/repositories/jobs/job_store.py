from __future__ import annotations

import threading

from app.domain.generation_job import GenerationJob


class JobNotFoundError(Exception):
    """Raised when no job is stored under the given job_id."""


class JobStore:
    """In-memory storage for GenerationJob instances, keyed by job_id.

    No persistence: jobs are lost on backend restart (accepted trade-off for
    a single-user, Docker Compose-only deployment). Uses threading.Lock
    (not asyncio.Lock) because job execution runs on a background thread
    (see StartGenerationJobUsecase) while status polling happens on the
    request-handling thread -- these are genuinely separate OS threads, not
    just concurrent coroutines on one event loop.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = threading.Lock()

    def save(self, job: GenerationJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> GenerationJob:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError:
                raise JobNotFoundError(f"no job stored for job_id {job_id!r}") from None
