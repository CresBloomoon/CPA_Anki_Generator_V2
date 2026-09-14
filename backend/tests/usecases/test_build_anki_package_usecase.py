import pytest

from app.domain.card import Card, CardContentItem
from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
from app.usecases.build_anki_package_usecase import (
    BuildAnkiPackageUsecase,
    SectionIndexNotFoundError,
    SectionNotDownloadableError,
)


def _make_section(title: str) -> Section:
    return Section(
        title=title,
        page_range=PageRange(start_page=1, end_page=5),
        deck_path=DeckPath.from_string("Root::A"),
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
    )
    return Card(content=item, section_title=section.title, deck_path=section.deck_path)


class _FakeAnkiPackageRepository:
    def __init__(self) -> None:
        self.calls: list[list[Card]] = []

    def build_package(self, cards: list[Card]) -> bytes:
        self.calls.append(cards)
        return b"fake-apkg-bytes"


class TestBuildAnkiPackageUsecase:
    def test_all_sections_done_is_complete_true(self) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )
        job.mark_running(0)
        cards1 = [_make_card("card-1", section1)]
        job.mark_done(0, cards1)
        job.mark_running(1)
        cards2 = [_make_card("card-2", section2)]
        job.mark_done(1, cards2)

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute(job)

        assert result.is_complete is True
        assert result.apkg_bytes == b"fake-apkg-bytes"
        assert repository.calls == [cards1 + cards2]

    def test_partial_completion_is_complete_false_and_uses_only_done_cards(
        self,
    ) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        section3 = _make_section("03節 C")
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[
                SectionJob(section=section1),
                SectionJob(section=section2),
                SectionJob(section=section3),
            ],
        )
        job.mark_running(0)
        done_cards = [_make_card("card-1", section1)]
        job.mark_done(0, done_cards)
        job.mark_running(1)
        job.mark_failed(1, "boom")
        # section3 left PENDING

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute(job)

        assert result.is_complete is False
        assert repository.calls == [done_cards]

    def test_partially_done_sections_cards_are_included(self) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )
        job.mark_running(0)
        done_cards = [_make_card("card-1", section1)]
        job.mark_done(0, done_cards)

        job.mark_running(1)
        partial_cards = [_make_card("card-2", section2)]
        job.section_jobs[1].cards.extend(partial_cards)
        job.mark_failed(1, "boom")

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute(job)

        assert job.section_jobs[1].status.name == "PARTIALLY_DONE"
        assert result.is_complete is False
        assert repository.calls == [done_cards + partial_cards]

    def test_no_sections_done_yet_still_produces_a_result(self) -> None:
        section1 = _make_section("01節 A")
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute(job)

        assert result.is_complete is False
        assert repository.calls == [[]]


class TestExecuteForSection:
    def test_done_section_returns_only_that_sections_cards(self) -> None:
        section1 = _make_section("01節 A")
        section2 = _make_section("02節 B")
        job = GenerationJob(
            job_id="job-1",
            section_jobs=[SectionJob(section=section1), SectionJob(section=section2)],
        )
        job.mark_running(0)
        cards1 = [_make_card("card-1", section1)]
        job.mark_done(0, cards1)
        job.mark_running(1)
        cards2 = [_make_card("card-2", section2)]
        job.mark_done(1, cards2)

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute_for_section(job, 0)

        assert result.is_complete is True
        assert result.apkg_bytes == b"fake-apkg-bytes"
        # Only section1's cards -- section2's cards2 must not leak in.
        assert repository.calls == [cards1]

    def test_partially_done_section_is_complete_false(self) -> None:
        section1 = _make_section("01節 A")
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])
        job.mark_running(0)
        partial_cards = [_make_card("card-1", section1)]
        job.section_jobs[0].cards.extend(partial_cards)
        job.mark_failed(0, "boom")
        assert job.section_jobs[0].status.name == "PARTIALLY_DONE"

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute_for_section(job, 0)

        assert result.is_complete is False
        assert repository.calls == [partial_cards]

    @pytest.mark.parametrize(
        "behavior",
        ["pending", "running", "failed_with_no_cards"],
    )
    def test_not_yet_downloadable_section_raises(self, behavior: str) -> None:
        section1 = _make_section("01節 A")
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])
        if behavior in ("running", "failed_with_no_cards"):
            job.mark_running(0)
        if behavior == "failed_with_no_cards":
            job.mark_failed(0, "boom")

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        with pytest.raises(SectionNotDownloadableError):
            usecase.execute_for_section(job, 0)
        assert repository.calls == []

    @pytest.mark.parametrize("section_index", [1, -1])
    def test_out_of_range_section_index_raises(self, section_index: int) -> None:
        section1 = _make_section("01節 A")
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])
        job.mark_running(0)
        job.mark_done(0, [_make_card("card-1", section1)])

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        with pytest.raises(SectionIndexNotFoundError):
            usecase.execute_for_section(job, section_index)
        assert repository.calls == []
