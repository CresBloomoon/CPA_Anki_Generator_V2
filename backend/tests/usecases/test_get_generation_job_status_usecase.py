import pytest

from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.job_store import JobNotFoundError, JobStore
from app.usecases.get_generation_job_status_usecase import (
    GetGenerationJobStatusUsecase,
)


def _make_job(job_id: str) -> GenerationJob:
    section = Section(
        title="01節 X",
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("Root::A"),
        source_file="book.pdf",
    )
    return GenerationJob(job_id=job_id, section_jobs=[SectionJob(section=section)])


class TestGetGenerationJobStatusUsecase:
    def test_returns_the_stored_job(self) -> None:
        job_store = JobStore()
        job = _make_job("job-1")
        job_store.save(job)
        usecase = GetGenerationJobStatusUsecase(job_store)

        result = usecase.execute("job-1")

        assert result is job

    def test_missing_job_id_raises(self) -> None:
        job_store = JobStore()
        usecase = GetGenerationJobStatusUsecase(job_store)

        with pytest.raises(JobNotFoundError):
            usecase.execute("missing-job")
