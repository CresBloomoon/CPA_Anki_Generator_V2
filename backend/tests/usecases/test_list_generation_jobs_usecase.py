from datetime import datetime, timezone

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.job_store import JobStore
from app.usecases.list_generation_jobs_usecase import ListGenerationJobsUsecase


def _make_job(job_id: str, created_at: datetime) -> GenerationJob:
    section = Section(
        title="01節 X",
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("Root::A"),
        source_file="book.pdf",
    )
    return GenerationJob(
        job_id=job_id,
        section_jobs=[SectionJob(section=section)],
        created_at=created_at,
    )


class TestListGenerationJobsUsecase:
    def test_returns_an_empty_list_when_no_jobs_exist(self) -> None:
        usecase = ListGenerationJobsUsecase(JobStore())

        assert usecase.execute() == []

    def test_returns_jobs_sorted_newest_first(self) -> None:
        job_store = JobStore()
        oldest = _make_job("job-oldest", datetime(2026, 1, 1, tzinfo=timezone.utc))
        middle = _make_job("job-middle", datetime(2026, 1, 2, tzinfo=timezone.utc))
        newest = _make_job("job-newest", datetime(2026, 1, 3, tzinfo=timezone.utc))
        # Saved out of order on purpose -- the usecase must sort, not rely
        # on insertion order.
        job_store.save(middle)
        job_store.save(oldest)
        job_store.save(newest)
        usecase = ListGenerationJobsUsecase(job_store)

        result = usecase.execute()

        assert [job.job_id for job in result] == [
            "job-newest",
            "job-middle",
            "job-oldest",
        ]
