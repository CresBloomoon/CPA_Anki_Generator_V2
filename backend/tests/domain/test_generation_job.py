import pytest

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import GenerationJob, SectionJob, SectionJobStatus
from app.domain.section import DeckPath, PageRange, Section


def _make_section(title: str) -> Section:
    return Section(
        title=title,
        chapter_title="01章 総論",
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("公認会計士試験::財務会計論"),
        min_card_count=1,
        source_file="textbook.pdf",
    )


def _make_card(section_title: str) -> Card:
    item = CardContentItem(
        title="会計の意義",
        question="Q",
        ronsho_body="R",
        kaisetsu_body="K",
        yo_suruni_body="Y",
        ryui_body="特になし",
        rank_tanto="A",
        rank_ronbun="B",
        page_code="③-8-1",
    )
    return Card(
        content=item,
        section_title=section_title,
        deck_path=DeckPath.from_string("公認会計士試験::財務会計論"),
    )


def _make_job(section_count: int = 3) -> GenerationJob:
    section_jobs = [
        SectionJob(section=_make_section(f"0{i}節 論点{i}")) for i in range(1, section_count + 1)
    ]
    return GenerationJob(job_id="job-1", section_jobs=section_jobs)


class TestGenerationJobConstruction:
    def test_empty_job_id_raises(self) -> None:
        with pytest.raises(ValueError):
            GenerationJob(job_id="", section_jobs=[SectionJob(section=_make_section("01節"))])

    def test_empty_section_jobs_raises(self) -> None:
        with pytest.raises(ValueError):
            GenerationJob(job_id="job-1", section_jobs=[])


class TestStateTransitions:
    def test_mark_running_from_pending_succeeds(self) -> None:
        job = _make_job(1)
        job.mark_running(0)
        assert job.section_jobs[0].status == SectionJobStatus.RUNNING

    def test_mark_running_from_non_pending_raises(self) -> None:
        job = _make_job(1)
        job.mark_running(0)
        with pytest.raises(ValueError):
            job.mark_running(0)

    def test_mark_done_from_running_succeeds(self) -> None:
        job = _make_job(1)
        job.mark_running(0)
        cards = [_make_card("01節 論点1")]
        job.mark_done(0, cards)
        assert job.section_jobs[0].status == SectionJobStatus.DONE
        assert job.section_jobs[0].cards == cards

    def test_mark_done_without_running_raises(self) -> None:
        job = _make_job(1)
        with pytest.raises(ValueError):
            job.mark_done(0, [])

    def test_mark_failed_from_running_succeeds(self) -> None:
        job = _make_job(1)
        job.mark_running(0)
        job.mark_failed(0, "AI呼び出しが失敗しました")
        assert job.section_jobs[0].status == SectionJobStatus.FAILED
        assert job.section_jobs[0].error_message == "AI呼び出しが失敗しました"

    def test_mark_failed_without_running_raises(self) -> None:
        job = _make_job(1)
        with pytest.raises(ValueError):
            job.mark_failed(0, "エラー")


class TestIsComplete:
    def test_true_when_all_done(self) -> None:
        job = _make_job(2)
        for index in range(2):
            job.mark_running(index)
            job.mark_done(index, [])
        assert job.is_complete() is True

    def test_false_when_some_pending(self) -> None:
        job = _make_job(2)
        job.mark_running(0)
        job.mark_done(0, [])
        assert job.is_complete() is False

    def test_false_when_some_failed(self) -> None:
        job = _make_job(2)
        job.mark_running(0)
        job.mark_failed(0, "エラー")
        job.mark_running(1)
        job.mark_done(1, [])
        assert job.is_complete() is False


class TestCollectGeneratedCards:
    def test_returns_only_done_sections_cards_when_one_failed_and_rest_pending(
        self,
    ) -> None:
        # Reproduces the legacy UX contract: one section fails after retries
        # are exhausted, the remaining sections are left untouched (aborted
        # batch), but cards from sections that already completed must not be
        # lost.
        job = _make_job(3)
        done_cards = [_make_card("01節 論点1")]

        job.mark_running(0)
        job.mark_done(0, done_cards)

        job.mark_running(1)
        job.mark_failed(1, "AI呼び出しが失敗しました")

        # index 2 stays PENDING (batch aborted before reaching it)

        assert job.section_jobs[2].status == SectionJobStatus.PENDING
        assert job.collect_generated_cards() == done_cards
