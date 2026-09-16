from __future__ import annotations

import json
from pathlib import Path

from app.domain.generation_job import GenerationJob
from app.repositories.jobs.generation_job_serializer import job_from_dict, job_to_dict

_DEFAULT_JOBS_DIR = Path(__file__).resolve().parents[3] / "data" / "generation_jobs"


class GenerationJobRepository:
    """Persists each GenerationJob as its own JSON file, keyed by job_id.

    One file per job (rather than one shared file for all jobs) so that
    writing one job's progress never requires rewriting every other job's
    data (see Phase7-2's dev-log). Bind-mounted into the backend container
    the same way as RootPathHistoryRepository's file (see docker-compose.yml
    and .gitignore's backend/data/ entry).
    """

    def __init__(self, jobs_dir: Path = _DEFAULT_JOBS_DIR) -> None:
        self._jobs_dir = jobs_dir

    def save(self, job: GenerationJob) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._job_path(job.job_id).write_text(
            json.dumps(job_to_dict(job), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, job_id: str) -> GenerationJob | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        return job_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _job_path(self, job_id: str) -> Path:
        return self._jobs_dir / f"{job_id}.json"
