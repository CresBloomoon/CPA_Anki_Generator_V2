from pathlib import Path

import pytest

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.generation_job_repository import GenerationJobRepository
from app.repositories.jobs.job_store import JobNotFoundError, JobStore


def _make_job(job_id: str = "job-1", idempotency_key: str = "") -> GenerationJob:
    section = Section(
        title="01節 X",
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("Root::A"),
        source_file="book.pdf",
    )
    return GenerationJob(
        job_id=job_id,
        section_jobs=[SectionJob(section=section)],
        idempotency_key=idempotency_key,
    )


class _SpyGenerationJobRepository(GenerationJobRepository):
    """Counts get() calls to verify JobStore caches a fallback result
    instead of re-reading the repository on every subsequent get().
    """

    def __init__(self, jobs_dir: Path) -> None:
        super().__init__(jobs_dir=jobs_dir)
        self.get_calls = 0

    def get(self, job_id: str) -> GenerationJob | None:
        self.get_calls += 1
        return super().get(job_id)


class TestJobStore:
    def test_save_then_get_round_trips(self) -> None:
        store = JobStore()
        job = _make_job("job-1")

        store.save(job)

        assert store.get("job-1") is job

    def test_get_missing_job_id_raises(self) -> None:
        store = JobStore()

        with pytest.raises(JobNotFoundError):
            store.get("missing-job")

    def test_get_reflects_mutations_made_after_save(self) -> None:
        # The store holds the same mutable GenerationJob object; mutating
        # it after saving must be visible through get() without saving
        # again, since StartGenerationJobUsecase relies on this.
        store = JobStore()
        job = _make_job("job-1")
        store.save(job)

        job.mark_running(0)

        from app.domain.generation_job import SectionJobStatus

        assert store.get("job-1").section_jobs[0].status == SectionJobStatus.RUNNING

    def test_different_job_ids_are_stored_independently(self) -> None:
        store = JobStore()
        job1 = _make_job("job-1")
        job2 = _make_job("job-2")

        store.save(job1)
        store.save(job2)

        assert store.get("job-1") is job1
        assert store.get("job-2") is job2

    def test_find_by_idempotency_key_returns_the_matching_job(self) -> None:
        store = JobStore()
        job = _make_job("job-1", idempotency_key="abc123")
        store.save(job)

        assert store.find_by_idempotency_key("abc123") is job

    def test_find_by_idempotency_key_returns_none_when_no_match(self) -> None:
        store = JobStore()
        store.save(_make_job("job-1", idempotency_key="abc123"))

        assert store.find_by_idempotency_key("does-not-exist") is None

    def test_find_by_idempotency_key_returns_a_match_even_if_already_complete(
        self,
    ) -> None:
        # Plain lookup only -- whether a match "still counts" as a
        # duplicate (e.g. because it's already complete) is
        # StartGenerationJobUsecase's decision, not JobStore's (see
        # Phase4-9's dev-log).
        store = JobStore()
        job = _make_job("job-1", idempotency_key="abc123")
        job.mark_running(0)
        job.mark_done(0, [])
        store.save(job)

        assert job.is_complete()
        assert store.find_by_idempotency_key("abc123") is job


class TestPersistence:
    def test_save_without_a_repository_does_not_touch_disk(
        self, tmp_path: Path
    ) -> None:
        # No GenerationJobRepository given -- must behave exactly as before
        # (in-memory only), and must not create any files.
        store = JobStore()

        store.save(_make_job("job-1"))

        assert list(tmp_path.iterdir()) == []

    def test_save_with_a_repository_writes_through_to_disk(
        self, tmp_path: Path
    ) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        store = JobStore(repository)
        job = _make_job("job-1")

        store.save(job)

        assert repository.get("job-1") == job

    def test_get_still_reads_from_the_in_memory_dict_not_the_repository(
        self, tmp_path: Path
    ) -> None:
        # On a memory hit, get() must return the exact in-memory object --
        # not fall back to the repository at all (see Phase7-2-3's
        # dev-log). A repository round-trip would produce an equal but
        # distinct object, so identity (`is`) is what actually
        # distinguishes "returned from memory" from "fell back to disk"
        # here.
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        store = JobStore(repository)
        job = _make_job("job-1")
        store.save(job)

        assert store.get("job-1") is job


class TestFallbackToRepository:
    def test_get_falls_back_to_the_repository_when_missing_from_memory(
        self, tmp_path: Path
    ) -> None:
        # Simulates a backend restart: the job was written to disk by a
        # previous save() (possibly in a previous process), but this
        # JobStore's in-memory dict starts out empty.
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        repository.save(_make_job("job-1"))
        store = JobStore(repository)

        assert store.get("job-1") == _make_job("job-1")

    def test_get_caches_the_repository_fallback_result(self, tmp_path: Path) -> None:
        # The second get() for the same job_id must be served from memory
        # -- not read the repository again (see Phase7-2-3's dev-log).
        repository = _SpyGenerationJobRepository(tmp_path)
        repository.save(_make_job("job-1"))
        store = JobStore(repository)

        first = store.get("job-1")
        second = store.get("job-1")

        assert repository.get_calls == 1
        assert second is first

    def test_get_raises_when_missing_from_both_memory_and_the_repository(
        self, tmp_path: Path
    ) -> None:
        # Distinct from test_get_missing_job_id_raises above, which uses a
        # JobStore with no repository at all -- this covers the case where
        # a repository *is* configured but simply has no file for this
        # job_id either.
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        store = JobStore(repository)

        with pytest.raises(JobNotFoundError):
            store.get("missing-job")
