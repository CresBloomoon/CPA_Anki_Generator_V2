from datetime import datetime, timedelta, timezone

import pytest

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import (
    GenerationJob,
    SectionJob,
    SectionJobStatus,
    TokenUsage,
)
from app.domain.section import DeckPath, PageRange, Section


def _make_section(title: str) -> Section:
    return Section(
        title=title,
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("公認会計士試験::財務会計論"),
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

    def test_additional_prompt_defaults_to_empty_string(self) -> None:
        job = _make_job(1)
        assert job.additional_prompt == ""

    def test_additional_prompt_can_be_set_explicitly(self) -> None:
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=_make_section("01節"))],
            additional_prompt="具体例を厚めに",
        )
        assert job.additional_prompt == "具体例を厚めに"

    def test_idempotency_key_defaults_to_empty_string(self) -> None:
        job = _make_job(1)
        assert job.idempotency_key == ""

    def test_idempotency_key_can_be_set_explicitly(self) -> None:
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=_make_section("01節"))],
            idempotency_key="abc123",
        )
        assert job.idempotency_key == "abc123"


class TestStateTransitions:
    def test_mark_running_from_pending_succeeds(self) -> None:
        job = _make_job(1)
        job.mark_running(0)
        assert job.section_jobs[0].status == SectionJobStatus.RUNNING
        assert job.section_jobs[0].started_at is not None

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
        assert job.section_jobs[0].finished_at is not None

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
        assert job.section_jobs[0].finished_at is not None

    def test_mark_failed_without_running_raises(self) -> None:
        job = _make_job(1)
        with pytest.raises(ValueError):
            job.mark_failed(0, "エラー")

    def test_mark_failed_with_cards_already_present_becomes_partially_done(
        self,
    ) -> None:
        # Reproduces GenerateCardsForSectionUsecase's on_block_generated
        # callback having already appended earlier blocks' cards onto this
        # section_job (see StartGenerationJobUsecase) before a later block
        # fails. The section produced *some* usable output, so it must not
        # be conflated with a total failure.
        job = _make_job(1)
        job.mark_running(0)
        partial_cards = [_make_card("01節 論点1")]
        job.section_jobs[0].cards.extend(partial_cards)

        job.mark_failed(0, "ブロック2/3でAI呼び出しが失敗しました")

        assert job.section_jobs[0].status == SectionJobStatus.PARTIALLY_DONE
        assert job.section_jobs[0].cards == partial_cards
        assert job.section_jobs[0].error_message == "ブロック2/3でAI呼び出しが失敗しました"


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

    def test_false_when_some_partially_done(self) -> None:
        job = _make_job(2)
        job.mark_running(0)
        job.section_jobs[0].cards.append(_make_card("01節 論点1"))
        job.mark_failed(0, "エラー")
        job.mark_running(1)
        job.mark_done(1, [])
        assert job.section_jobs[0].status == SectionJobStatus.PARTIALLY_DONE
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

    def test_partially_done_sections_cards_are_included(self) -> None:
        job = _make_job(2)
        done_cards = [_make_card("01節 論点1")]
        partial_cards = [_make_card("02節 論点2")]

        job.mark_running(0)
        job.mark_done(0, done_cards)

        job.mark_running(1)
        job.section_jobs[1].cards.extend(partial_cards)
        job.mark_failed(1, "AI呼び出しが失敗しました")

        assert job.section_jobs[1].status == SectionJobStatus.PARTIALLY_DONE
        assert job.collect_generated_cards() == done_cards + partial_cards


class TestElapsedSeconds:
    def test_pending_section_has_no_elapsed_seconds(self) -> None:
        job = _make_job(1)
        assert job.section_jobs[0].elapsed_seconds() is None

    def test_running_section_elapsed_seconds_measures_against_now(self) -> None:
        # finished_at left unset (still RUNNING) -- elapsed_seconds() must
        # keep advancing against the current time, not freeze at 0 (see
        # Phase4-6's dev-log).
        section_job = SectionJob(
            section=_make_section("01節"),
            status=SectionJobStatus.RUNNING,
            started_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        assert section_job.elapsed_seconds() >= 5

    def test_finished_section_elapsed_seconds_is_frozen(self) -> None:
        started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        finished_at = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        section_job = SectionJob(
            section=_make_section("01節"),
            status=SectionJobStatus.DONE,
            started_at=started_at,
            finished_at=finished_at,
        )
        assert section_job.elapsed_seconds() == 10


class TestTokenUsage:
    def test_total_tokens_is_input_plus_output(self) -> None:
        assert TokenUsage(10, 20).total_tokens == 30

    def test_add_sums_both_fields(self) -> None:
        assert TokenUsage(10, 20) + TokenUsage(1, 2) == TokenUsage(11, 22)

    def test_section_job_token_usage_defaults_to_zero(self) -> None:
        section_job = SectionJob(section=_make_section("01節"))
        assert section_job.token_usage == TokenUsage(0, 0)


class TestTotalTokenUsage:
    def test_zero_when_no_section_has_recorded_usage(self) -> None:
        job = _make_job(2)
        assert job.total_token_usage() == TokenUsage(0, 0)

    def test_sums_across_all_sections(self) -> None:
        job = _make_job(2)
        job.section_jobs[0].token_usage = TokenUsage(10, 20)
        job.section_jobs[1].token_usage = TokenUsage(5, 7)
        assert job.total_token_usage() == TokenUsage(15, 27)

    def test_includes_failed_sections_unlike_collect_generated_cards(self) -> None:
        # Tokens spent on a FAILED section were still actually billed, so
        # total_token_usage() must not filter by status the way
        # collect_generated_cards() does (see the token-usage-display
        # feature's dev-log).
        job = _make_job(2)
        job.mark_running(0)
        job.section_jobs[0].token_usage = TokenUsage(10, 20)
        job.mark_failed(0, "エラー")
        job.mark_running(1)
        job.mark_done(1, [])

        assert job.section_jobs[0].status == SectionJobStatus.FAILED
        assert job.collect_generated_cards() == []
        assert job.total_token_usage() == TokenUsage(10, 20)
