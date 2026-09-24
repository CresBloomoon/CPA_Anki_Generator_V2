import json
from datetime import datetime, timezone
from pathlib import Path

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import (
    GenerationJob,
    SectionJob,
    SectionJobStatus,
    TokenUsage,
)
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.generation_job_repository import GenerationJobRepository
from app.repositories.jobs.generation_job_serializer import job_to_dict


def _make_section(title: str, deck_path: str, end_page: int | None) -> Section:
    return Section(
        title=title,
        page_range=PageRange(start_page=1, end_page=end_page),
        deck_path=DeckPath.from_string(deck_path),
        source_file="book.pdf",
    )


def _make_card(title: str, section: Section) -> Card:
    item = CardContentItem(
        title=title,
        question="Q",
        ronsho_body="R",
        kaisetsu_body="K",
        yo_suruni_body="Y",
        ryui_body="特になし",
        rank_tanto="A",
        rank_ronbun="B",
        page_code="1-1-1",
        tags=("tag1", "tag2"),
    )
    return Card(content=item, section_title=section.title, deck_path=section.deck_path)


class TestGenerationJobRepository:
    def test_get_returns_none_when_no_file_exists(self, tmp_path: Path) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)

        assert repository.get("missing-job") is None

    def test_save_then_get_round_trips_a_fully_populated_job(
        self, tmp_path: Path
    ) -> None:
        # Exercises every field that needs explicit conversion at the JSON
        # boundary (see generation_job_serializer.py): SectionJobStatus
        # (Enum), started_at/finished_at (datetime), DeckPath.segments
        # (tuple), and CardContentItem.tags (tuple) -- plus a PENDING
        # section_job with both timestamps left as None.
        repository = GenerationJobRepository(jobs_dir=tmp_path)

        section1 = _make_section("01節 A", "Root::A", end_page=10)
        section2 = _make_section("02節 B", "Root::B", end_page=None)
        section3 = _make_section("03節 C", "Root::C", end_page=20)

        done_section_job = SectionJob(
            section=section1,
            status=SectionJobStatus.DONE,
            cards=[_make_card("card-1", section1)],
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
            token_usage=TokenUsage(input_tokens=16, output_tokens=103),
        )
        partially_done_section_job = SectionJob(
            section=section2,
            status=SectionJobStatus.PARTIALLY_DONE,
            cards=[_make_card("card-2", section2)],
            error_message="ブロック2/2でAI呼び出しが失敗しました",
            started_at=datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc),
            finished_at=datetime(2026, 1, 1, 0, 7, tzinfo=timezone.utc),
            token_usage=TokenUsage(input_tokens=8, output_tokens=40),
        )
        pending_section_job = SectionJob(section=section3)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[
                done_section_job,
                partially_done_section_job,
                pending_section_job,
            ],
            additional_prompt="具体例を厚めに",
            idempotency_key="abc123",
            root_path="公認会計士試験::監査論",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        repository.save(job)
        loaded = repository.get("job-1")

        assert loaded == job

    def test_save_creates_one_file_per_job(self, tmp_path: Path) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        section = _make_section("01節 A", "Root::A", end_page=5)

        repository.save(
            GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section)])
        )
        repository.save(
            GenerationJob(job_id="job-2", section_jobs=[SectionJob(section=section)])
        )

        assert (tmp_path / "job-1.json").exists()
        assert (tmp_path / "job-2.json").exists()

    def test_save_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        nested_dir = tmp_path / "nested" / "generation_jobs"
        repository = GenerationJobRepository(jobs_dir=nested_dir)
        section = _make_section("01節 A", "Root::A", end_page=5)

        repository.save(
            GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section)])
        )

        assert nested_dir.exists()


class TestListAll:
    def test_returns_an_empty_list_when_the_directory_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path / "generation_jobs")

        assert repository.list_all() == []

    def test_returns_an_empty_list_when_the_directory_is_empty(
        self, tmp_path: Path
    ) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)

        assert repository.list_all() == []

    def test_returns_every_saved_job(self, tmp_path: Path) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        section = _make_section("01節 A", "Root::A", end_page=5)
        job1 = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section)])
        job2 = GenerationJob(job_id="job-2", section_jobs=[SectionJob(section=section)])

        repository.save(job1)
        repository.save(job2)

        loaded = repository.list_all()
        assert {job.job_id for job in loaded} == {"job-1", "job-2"}


class TestBackwardCompatibility:
    # Phase7-2-5's dev-log: a job file persisted before Phase7-2-4 added
    # created_at has no such key at all -- job_from_dict() must tolerate
    # that instead of raising KeyError (which used to take down the whole
    # GET /generation-jobs list with a single old file mixed in).
    def test_get_loads_a_file_missing_created_at_without_raising(
        self, tmp_path: Path
    ) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        section = _make_section("01節 A", "Root::A", end_page=5)
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section)])
        data = job_to_dict(job)
        del data["created_at"]
        (tmp_path / "job-1.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        loaded = repository.get("job-1")

        assert loaded is not None
        assert loaded.job_id == "job-1"
        # Falls back to the earliest possible timestamp so this job sorts
        # to the very end of a newest-first list, standing in for "unknown".
        assert loaded.created_at == datetime.min.replace(tzinfo=timezone.utc)

    def test_list_all_still_returns_other_jobs_when_one_file_is_missing_created_at(
        self, tmp_path: Path
    ) -> None:
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        section = _make_section("01節 A", "Root::A", end_page=5)

        old_job = GenerationJob(
            job_id="old-job", section_jobs=[SectionJob(section=section)]
        )
        old_data = job_to_dict(old_job)
        del old_data["created_at"]
        (tmp_path / "old-job.json").write_text(
            json.dumps(old_data, ensure_ascii=False), encoding="utf-8"
        )

        repository.save(
            GenerationJob(job_id="new-job", section_jobs=[SectionJob(section=section)])
        )

        loaded = repository.list_all()
        assert {job.job_id for job in loaded} == {"old-job", "new-job"}

    def test_get_loads_a_file_missing_token_usage_without_raising(
        self, tmp_path: Path
    ) -> None:
        # A file persisted before the token-usage-display feature added
        # SectionJob.token_usage has no such key at all -- same shape of
        # incident as the created_at one above.
        repository = GenerationJobRepository(jobs_dir=tmp_path)
        section = _make_section("01節 A", "Root::A", end_page=5)
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section)])
        data = job_to_dict(job)
        del data["section_jobs"][0]["token_usage"]
        (tmp_path / "job-1.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        loaded = repository.get("job-1")

        assert loaded is not None
        assert loaded.section_jobs[0].token_usage == TokenUsage(0, 0)
