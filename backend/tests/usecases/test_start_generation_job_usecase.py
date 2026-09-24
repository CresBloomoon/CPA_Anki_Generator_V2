import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import (
    GenerationJob,
    SectionJob,
    SectionJobStatus,
    TokenUsage,
)
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.generation_job_repository import GenerationJobRepository
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore
from app.usecases.start_generation_job_usecase import (
    DuplicateGenerationJobError,
    StartGenerationJobUsecase,
)


def _make_section(title: str, source_file: str = "book.pdf") -> Section:
    return Section(
        title=title,
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("Root::A"),
        source_file=source_file,
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
    )
    return Card(content=item, section_title=section.title, deck_path=section.deck_path)


class _SpyJobStore(JobStore):
    """Counts save() calls to verify run() persists after each transition.

    See test_run_persists_state_after_each_transition/..._even_when_a_
    section_fails below -- these check the *trigger points*, while
    GenerationJobRepository's own round-trip test (see Phase7-2's dev-log)
    checks the actual on-disk content.
    """

    def __init__(self) -> None:
        super().__init__()
        self.save_calls = 0

    def save(self, job: GenerationJob) -> None:
        self.save_calls += 1
        super().save(job)


class _RecordingGenerationJobRepository(GenerationJobRepository):
    """Records section_jobs[0]'s raw card count written on every save(), on
    top of the real on-disk write -- lets a test confirm writes happen
    incrementally, one per block, rather than only checking the final
    on-disk content.

    Deliberately reads section_job.cards directly rather than
    job.collect_generated_cards(): the latter only counts DONE/
    PARTIALLY_DONE section_jobs (a confirmed-complete-cards view, by
    design -- see Phase1-4's dev-log), so it stays 0 for a still-RUNNING
    section_job no matter how many cards have actually been extended onto
    it. What this test needs to observe is the raw count actually written
    to disk at each point, which section_job.cards reflects regardless of
    status (see Phase7-2-2's dev-log for the test failure this fixes).
    """

    def __init__(self, jobs_dir: Path) -> None:
        super().__init__(jobs_dir=jobs_dir)
        self.saved_card_counts: list[int] = []

    def save(self, job: GenerationJob) -> None:
        super().save(job)
        self.saved_card_counts.append(len(job.section_jobs[0].cards))


class _FakeGenerateCardsForSectionUsecase:
    def __init__(self, behavior) -> None:
        self._behavior = behavior
        self.calls: list[Section] = []
        self.additional_prompts: list[str] = []

    def execute(
        self,
        section: Section,
        pdf_bytes: bytes,
        additional_prompt: str = "",
        on_block_generated=None,
    ) -> list[Card]:
        self.calls.append(section)
        self.additional_prompts.append(additional_prompt)
        return self._behavior(section, on_block_generated)


class TestRun:
    def test_consecutive_failures_reaching_the_threshold_stops_the_batch_but_keeps_completed_sections(
        self,
    ) -> None:
        # The Phase3-3 acceptance scenario, updated for B-2: a single
        # failure no longer aborts the batch by itself (see
        # test_a_single_failure_does_not_stop_the_batch below) -- only
        # *consecutive* failures reaching the default threshold (2) do.
        # 4 sections: 1st succeeds, 2nd and 3rd fail back-to-back (hitting
        # the threshold), 4th is left untouched.
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        section3 = _make_section("03節 C")
        section4 = _make_section("04節 D")
        done_cards = [_make_card("card-1", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            if section is section1:
                return done_cards
            if section is section2:
                raise RuntimeError("2節でAI呼び出しが失敗しました")
            if section is section3:
                raise RuntimeError("3節でAI呼び出しが失敗しました")
            raise AssertionError("section4 must not be processed")

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[
                SectionJob(section=section1),
                SectionJob(section=section2),
                SectionJob(section=section3),
                SectionJob(section=section4),
            ],
        )

        usecase.run(job)

        assert job.section_jobs[0].status == SectionJobStatus.DONE
        assert job.section_jobs[1].status == SectionJobStatus.FAILED
        assert job.section_jobs[1].error_message == "2節でAI呼び出しが失敗しました"
        assert job.section_jobs[2].status == SectionJobStatus.FAILED
        assert job.section_jobs[2].error_message == "3節でAI呼び出しが失敗しました"
        assert job.section_jobs[3].status == SectionJobStatus.PENDING
        assert job.collect_generated_cards() == done_cards
        assert len(fake_generate.calls) == 3  # section4 was never attempted

    def test_a_single_failure_does_not_stop_the_batch(self) -> None:
        # B-2: a single section's failure is usually specific to that
        # section, not the whole batch -- the next section must still be
        # attempted.
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        section3 = _make_section("03節 C")
        cards1 = [_make_card("card-1", section1)]
        cards3 = [_make_card("card-3", section3)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            if section is section2:
                raise RuntimeError("2節でAI呼び出しが失敗しました")
            return cards1 if section is section1 else cards3

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[
                SectionJob(section=section1),
                SectionJob(section=section2),
                SectionJob(section=section3),
            ],
        )

        usecase.run(job)

        assert job.section_jobs[0].status == SectionJobStatus.DONE
        assert job.section_jobs[1].status == SectionJobStatus.FAILED
        assert job.section_jobs[2].status == SectionJobStatus.DONE
        assert len(fake_generate.calls) == 3  # section3 WAS attempted

    def test_success_resets_the_consecutive_failure_count(self) -> None:
        # 1 success -> 2 fail -> 3 success -> 4 fail -> 5 fail. Without the
        # reset-on-success, the failures at section2 and section4 would
        # already look "consecutive" and stop the batch right after
        # section4. With the reset, the count only reaches the default
        # threshold (2) at section5.
        section1 = _make_section("01節")
        section2 = _make_section("02節")
        section3 = _make_section("03節")
        section4 = _make_section("04節")
        section5 = _make_section("05節")
        section6 = _make_section("06節")
        cards1 = [_make_card("card-1", section1)]
        cards3 = [_make_card("card-3", section3)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            if section is section1:
                return cards1
            if section is section3:
                return cards3
            if section is section6:
                raise AssertionError("section6 must not be processed")
            raise RuntimeError(f"{section.title}でAI呼び出しが失敗しました")

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[
                SectionJob(section=section1),
                SectionJob(section=section2),
                SectionJob(section=section3),
                SectionJob(section=section4),
                SectionJob(section=section5),
                SectionJob(section=section6),
            ],
        )

        usecase.run(job)

        assert job.section_jobs[0].status == SectionJobStatus.DONE
        assert job.section_jobs[1].status == SectionJobStatus.FAILED
        assert job.section_jobs[2].status == SectionJobStatus.DONE
        assert job.section_jobs[3].status == SectionJobStatus.FAILED
        assert job.section_jobs[4].status == SectionJobStatus.FAILED
        assert job.section_jobs[5].status == SectionJobStatus.PENDING
        assert len(fake_generate.calls) == 5  # section6 was never attempted

    def test_cards_from_a_section_after_a_skipped_failure_are_collected(
        self,
    ) -> None:
        # B-2's "skip and continue" only matters if the cards from sections
        # processed *after* a skipped failure actually make it into
        # collect_generated_cards().
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        done_cards = [_make_card("card-2", section2)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            if section is section1:
                raise RuntimeError("1節でAI呼び出しが失敗しました")
            return done_cards

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )

        usecase.run(job)

        assert job.section_jobs[0].status == SectionJobStatus.FAILED
        assert job.section_jobs[1].status == SectionJobStatus.DONE
        assert job.collect_generated_cards() == done_cards

    def test_all_sections_succeed(self) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card(f"card-{section.title}", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )

        usecase.run(job)

        assert job.is_complete()
        assert len(job.collect_generated_cards()) == 2

    def test_job_additional_prompt_is_forwarded_to_every_section_call(self) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card(f"card-{section.title}", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
            additional_prompt="具体例を厚めに",
        )

        usecase.run(job)

        assert fake_generate.additional_prompts == ["具体例を厚めに", "具体例を厚めに"]

    def test_on_block_generated_persists_partial_cards_onto_the_failing_section(
        self,
    ) -> None:
        # Reproduces the incident this feature exists to prevent: a section
        # spanning multiple blocks succeeds on block 1 (cards generated,
        # API already billed) then fails on block 2. Without wiring
        # on_block_generated to section_job.cards, block 1's cards would be
        # silently discarded when the section ends up FAILED.
        section1 = _make_section("01節 A")
        partial_cards = [_make_card("block-1-card", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(partial_cards, TokenUsage(0, 0))
            raise RuntimeError("ブロック2/2でAI呼び出しが失敗しました")

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1", section_jobs=[SectionJob(section=section1)]
        )

        usecase.run(job)

        assert job.section_jobs[0].status == SectionJobStatus.PARTIALLY_DONE
        assert job.section_jobs[0].cards == partial_cards
        assert job.collect_generated_cards() == partial_cards

    def test_run_persists_state_after_each_transition(self) -> None:
        # See Phase7-2's dev-log: run() mutates the shared job object
        # directly, so persistence (when a GenerationJobRepository is
        # wired into JobStore) only happens if run() explicitly re-saves
        # after every mark_running/mark_done/mark_failed call. 2 sections,
        # both succeed: mark_running + mark_done for each = 4 saves.
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card(f"card-{section.title}", section)]

        job_store = _SpyJobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )

        usecase.run(job)

        assert job_store.save_calls == 4

    def test_run_persists_state_even_when_a_section_fails(self) -> None:
        section1 = _make_section("01節 A")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            raise RuntimeError("1節でAI呼び出しが失敗しました")

        job_store = _SpyJobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        # mark_running + mark_failed.
        assert job_store.save_calls == 2

    def test_run_persists_state_after_each_block_within_a_section(self) -> None:
        # A section split into 2 blocks: each on_block_generated call must
        # now also trigger a save(), on top of the section-level
        # mark_running/mark_done saves added in Phase7-2-1 (see
        # Phase7-2-2's dev-log).
        section1 = _make_section("01節 A")
        block1_cards = [_make_card("block-1", section1)]
        block2_cards = [_make_card("block-2", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(block1_cards, TokenUsage(0, 0))
            on_block_generated(block2_cards, TokenUsage(0, 0))
            return block1_cards + block2_cards

        job_store = _SpyJobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        # mark_running + block1 + block2 + mark_done = 4 saves.
        assert job_store.save_calls == 4
        assert job.section_jobs[0].cards == block1_cards + block2_cards

    def test_run_accumulates_token_usage_across_blocks(self) -> None:
        section1 = _make_section("01節 A")
        block1_cards = [_make_card("block-1", section1)]
        block2_cards = [_make_card("block-2", section1)]
        block1_usage = TokenUsage(input_tokens=10, output_tokens=20)
        block2_usage = TokenUsage(input_tokens=5, output_tokens=7)

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(block1_cards, block1_usage)
            on_block_generated(block2_cards, block2_usage)
            return block1_cards + block2_cards

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        assert job.section_jobs[0].token_usage == TokenUsage(
            input_tokens=15, output_tokens=27
        )

    def test_run_persists_state_after_a_partial_block_before_failing(self) -> None:
        section1 = _make_section("01節 A")
        partial_cards = [_make_card("block-1-card", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(partial_cards, TokenUsage(0, 0))
            raise RuntimeError("ブロック2/2でAI呼び出しが失敗しました")

        job_store = _SpyJobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        # mark_running + block1 + mark_failed = 3 saves.
        assert job_store.save_calls == 3

    def test_run_writes_to_disk_incrementally_as_each_block_completes(
        self, tmp_path: Path
    ) -> None:
        section1 = _make_section("01節 A")
        block1_cards = [_make_card("block-1", section1)]
        block2_cards = [_make_card("block-2", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(block1_cards, TokenUsage(0, 0))
            on_block_generated(block2_cards, TokenUsage(0, 0))
            return block1_cards + block2_cards

        repository = _RecordingGenerationJobRepository(tmp_path)
        job_store = JobStore(repository)
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        # mark_running(0 cards) -> block1(1) -> block2(2) -> mark_done(2).
        assert repository.saved_card_counts == [0, 1, 2, 2]
        loaded = repository.get("job-1")
        assert loaded is not None
        assert loaded.collect_generated_cards() == block1_cards + block2_cards

    def test_run_does_not_touch_disk_across_blocks_when_no_repository_is_configured(
        self, tmp_path: Path
    ) -> None:
        section1 = _make_section("01節 A")
        block1_cards = [_make_card("block-1", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            on_block_generated(block1_cards, TokenUsage(0, 0))
            return block1_cards

        job_store = JobStore()  # no GenerationJobRepository wired in
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        usecase.run(job)

        assert list(tmp_path.iterdir()) == []


class TestExecute:
    def test_returns_a_job_id_and_registers_the_job_immediately(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job_id = usecase.execute([section])

        assert isinstance(job_id, str) and job_id
        job = job_store.get(job_id)
        assert len(job.section_jobs) == 1

        # Wait for the background thread to finish (fake dependencies
        # respond instantly, so this should complete well within the
        # timeout under normal conditions).
        deadline = time.monotonic() + 2.0
        while not job.is_complete() and time.monotonic() < deadline:
            time.sleep(0.01)

        assert job.is_complete()
        assert len(job.collect_generated_cards()) == 1

    def test_additional_prompt_defaults_to_empty_string_on_the_job(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job_id = usecase.execute([section])

        assert job_store.get(job_id).additional_prompt == ""

    def test_additional_prompt_is_stored_on_the_job_when_given(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job_id = usecase.execute([section], additional_prompt="具体例を厚めに")

        assert job_store.get(job_id).additional_prompt == "具体例を厚めに"

    def test_root_path_defaults_to_empty_string_on_the_job(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job_id = usecase.execute([section])

        assert job_store.get(job_id).root_path == ""

    def test_root_path_is_stored_on_the_job_when_given(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        job_id = usecase.execute([section], root_path="公認会計士試験::監査論")

        assert job_store.get(job_id).root_path == "公認会計士試験::監査論"

    def test_created_at_is_set_to_roughly_now(self) -> None:
        section = _make_section("01節 A")
        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(
            lambda section, on_block_generated: [_make_card("card-1", section)]
        )
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        before = datetime.now(timezone.utc)
        job_id = usecase.execute([section])
        after = datetime.now(timezone.utc)

        created_at = job_store.get(job_id).created_at
        assert before <= created_at <= after


class TestDuplicateDetection:
    def test_duplicate_request_while_first_job_is_incomplete_raises(self) -> None:
        # Reproduces a double-click or an automatic retry (see Phase4-9's
        # dev-log): the first request's background thread is still
        # running (blocked on release_event) when the identical second
        # request arrives.
        section = _make_section("01節 A")
        release_event = threading.Event()

        def behavior(section: Section, on_block_generated) -> list[Card]:
            release_event.wait(timeout=2.0)
            return [_make_card("card-1", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        first_job_id = usecase.execute([section])
        first_job = job_store.get(first_job_id)
        assert not first_job.is_complete()

        try:
            with pytest.raises(DuplicateGenerationJobError):
                usecase.execute([section])
        finally:
            release_event.set()
            deadline = time.monotonic() + 2.0
            while not first_job.is_complete() and time.monotonic() < deadline:
                time.sleep(0.01)

    def test_same_request_is_allowed_again_after_the_first_job_completes(
        self,
    ) -> None:
        section = _make_section("01節 A")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card("card-1", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        first_job_id = usecase.execute([section])
        first_job = job_store.get(first_job_id)
        deadline = time.monotonic() + 2.0
        while not first_job.is_complete() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert first_job.is_complete()

        # Re-running the exact same request (e.g. to intentionally
        # regenerate) must be allowed once the earlier job is done.
        second_job_id = usecase.execute([section])

        assert second_job_id != first_job_id

    def test_different_additional_prompt_is_not_treated_as_duplicate(self) -> None:
        section = _make_section("01節 A")

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card("card-1", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        first_job_id = usecase.execute([section], additional_prompt="")
        second_job_id = usecase.execute([section], additional_prompt="具体例を厚めに")

        assert second_job_id != first_job_id

    def test_different_section_content_is_not_treated_as_duplicate(self) -> None:
        section_a = _make_section("01節 A")
        section_b = Section(
            title=section_a.title,
            page_range=section_a.page_range,
            deck_path=DeckPath.from_string("Root::Different"),
            source_file=section_a.source_file,
        )

        def behavior(section: Section, on_block_generated) -> list[Card]:
            return [_make_card("card-1", section)]

        job_store = JobStore()
        pdf_store = PdfStore()
        pdf_store.save("book.pdf", b"pdf-bytes")
        fake_generate = _FakeGenerateCardsForSectionUsecase(behavior)
        usecase = StartGenerationJobUsecase(job_store, pdf_store, fake_generate)

        first_job_id = usecase.execute([section_a])
        second_job_id = usecase.execute([section_b])

        assert second_job_id != first_job_id
