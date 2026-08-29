import pytest

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
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
