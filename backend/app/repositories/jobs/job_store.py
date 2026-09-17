from __future__ import annotations

import threading

from app.domain.generation_job import GenerationJob
from app.repositories.jobs.generation_job_repository import GenerationJobRepository


class JobNotFoundError(Exception):
    """Raised when no job is stored under the given job_id."""


class JobStore:
    """Keyed GenerationJob storage: memory-first, with a disk fallback.

    The in-memory dict is checked first and satisfies most reads (status
    polling and download routes call get() every couple of seconds while a
    job is active). When a GenerationJobRepository is supplied, save()
    writes through to disk (see Phase7-2-1's dev-log) and get() falls back
    to reading from it on a miss -- e.g. after a backend restart wiped the
    in-memory dict but the job's JSON file survived (see Phase7-2-3's
    dev-log). A job found this way is cached back into the in-memory dict
    (without writing back to the repository -- it just came from there) so
    later get() calls for the same job_id don't re-read from disk. Defaults
    to no repository (a miss just raises JobNotFoundError), so existing
    in-memory-only call sites and tests are unaffected.

    Uses threading.Lock (not asyncio.Lock) because job execution runs on a
    background thread (see StartGenerationJobUsecase) while status polling
    happens on the request-handling thread -- these are genuinely separate
    OS threads, not just concurrent coroutines on one event loop.
    """

    def __init__(
        self, generation_job_repository: GenerationJobRepository | None = None
    ) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = threading.Lock()
        self._generation_job_repository = generation_job_repository

    def save(self, job: GenerationJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            if self._generation_job_repository is not None:
                self._generation_job_repository.save(job)

    def get(self, job_id: str) -> GenerationJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job

            if self._generation_job_repository is not None:
                job = self._generation_job_repository.get(job_id)
                if job is not None:
                    self._jobs[job_id] = job
                    return job

            raise JobNotFoundError(f"no job stored for job_id {job_id!r}")

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
