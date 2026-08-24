import time

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import GenerationJob, SectionJob, SectionJobStatus
from app.domain.section import DeckPath, PageRange, Section
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore
from app.usecases.start_generation_job_usecase import StartGenerationJobUsecase


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
    def test_one_failure_stops_the_batch_but_keeps_completed_sections(self) -> None:
        # The Phase3-3 acceptance scenario: 3 sections, the 2nd fails.
        # Expected: 1st DONE, 2nd FAILED, 3rd left PENDING, and
        # collect_generated_cards() returns only the 1st section's cards.
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        section3 = _make_section("03節 C")
        done_cards = [_make_card("card-1", section1)]

        def behavior(section: Section, on_block_generated) -> list[Card]:
            if section is section1:
                return done_cards
            if section is section2:
                raise RuntimeError("AI呼び出しが失敗しました")
            raise AssertionError("section3 must not be processed")

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
        assert job.section_jobs[1].error_message == "AI呼び出しが失敗しました"
        assert job.section_jobs[2].status == SectionJobStatus.PENDING
        assert job.collect_generated_cards() == done_cards
        assert len(fake_generate.calls) == 2  # section3 was never attempted

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
            on_block_generated(partial_cards)
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
