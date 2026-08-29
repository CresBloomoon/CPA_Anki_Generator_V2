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

    def find_by_idempotency_key(self, key: str) -> GenerationJob | None:
        # Plain lookup only -- no notion of "does this still count as a
        # duplicate" (e.g. whether the match is already complete) lives
        # here. That policy belongs to StartGenerationJobUsecase, the same
        # way B-2's consecutive-failure threshold does (see Phase4-9's
        # dev-log).
        with self._lock:
            for job in self._jobs.values():
                if job.idempotency_key == key:
                    return job
        return None
