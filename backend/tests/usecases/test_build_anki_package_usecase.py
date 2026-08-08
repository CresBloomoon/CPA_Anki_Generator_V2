from app.domain.card import Card, CardContentItem
from app.domain.generation_job import GenerationJob, SectionJob
from app.domain.section import DeckPath, PageRange, Section
from app.usecases.build_anki_package_usecase import BuildAnkiPackageUsecase


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

    def test_no_sections_done_yet_still_produces_a_result(self) -> None:
        section1 = _make_section("01節 A")
        job = GenerationJob(job_id="job-1", section_jobs=[SectionJob(section=section1)])

        repository = _FakeAnkiPackageRepository()
        usecase = BuildAnkiPackageUsecase(repository)

        result = usecase.execute(job)

        assert result.is_complete is False
        assert repository.calls == [[]]
