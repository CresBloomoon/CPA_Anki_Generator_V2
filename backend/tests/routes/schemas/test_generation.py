import pytest
from pydantic import ValidationError

from app.routes.schemas.generation import SectionInput, StartGenerationRequest


class TestSectionInput:
    def test_accepts_valid_values(self) -> None:
        section = SectionInput(
            title="第01節 会計の意義",
            start_page=2,
            end_page=5,
            deck_path="公認会計士試験::財務会計論::第01章 総論::第01節 会計の意義",
            source_file="book.pdf",
        )

        assert section.start_page == 2
        assert section.end_page == 5

    def test_allows_end_page_to_be_omitted(self) -> None:
        section = SectionInput(
            title="第01節 会計の意義",
            start_page=2,
            deck_path="Root::第01節 会計の意義",
            source_file="book.pdf",
        )

        assert section.end_page is None

    def test_rejects_start_page_below_one(self) -> None:
        with pytest.raises(ValidationError):
            SectionInput(
                title="第01節 会計の意義",
                start_page=0,
                deck_path="Root::第01節 会計の意義",
                source_file="book.pdf",
            )


class TestStartGenerationRequest:
    def test_defaults_additional_prompt_to_empty_string(self) -> None:
        request = StartGenerationRequest(
            sections=[
                SectionInput(
                    title="第01節 会計の意義",
                    start_page=2,
                    deck_path="Root::第01節 会計の意義",
                    source_file="book.pdf",
                )
            ]
        )

        assert request.additional_prompt == ""

    def test_holds_a_list_of_sections(self) -> None:
        request = StartGenerationRequest(
            sections=[
                SectionInput(
                    title="第01節 会計の意義",
                    start_page=2,
                    deck_path="Root::第01節 会計の意義",
                    source_file="book.pdf",
                ),
                SectionInput(
                    title="第02節 会計公準",
                    start_page=6,
                    deck_path="Root::第02節 会計公準",
                    source_file="book.pdf",
                ),
            ],
            additional_prompt="特に具体例を厚めに",
        )

        assert len(request.sections) == 2
        assert request.additional_prompt == "特に具体例を厚めに"
