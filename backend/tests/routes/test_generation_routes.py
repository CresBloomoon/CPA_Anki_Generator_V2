import time

import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    get_ai_card_generator_repository,
    get_job_store,
    get_pdf_store,
)
from app.domain.card import CardContent, CardContentItem
from app.main import app
from app.repositories.ai.base import AiCardGeneratorRepository
from app.repositories.ai.dto import PromptContext
from app.repositories.jobs.job_store import JobStore
from app.repositories.pdf.pdf_store import PdfStore


class _FakeAiRepository(AiCardGeneratorRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[str, PromptContext]] = []

    def generate_cards(
        self, section_text: str, prompt_context: PromptContext
    ) -> CardContent:
        self.calls.append((section_text, prompt_context))
        item = CardContentItem(
            title="card",
            question="Q",
            ronsho_body="R",
            kaisetsu_body="K",
            yo_suruni_body="Y",
            ryui_body="特になし",
            rank_tanto="A",
            rank_ronbun="B",
            page_code="1-1-1",
        )
        return CardContent(items=(item,))


@pytest.fixture()
def client():
    test_pdf_store = PdfStore()
    test_job_store = JobStore()
    app.dependency_overrides[get_pdf_store] = lambda: test_pdf_store
    app.dependency_overrides[get_job_store] = lambda: test_job_store
    app.dependency_overrides[get_ai_card_generator_repository] = _FakeAiRepository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _build_fixture_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "会計の意義について説明する。")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _upload_fixture_pdf(client: TestClient, filename: str = "book.pdf") -> None:
    client.post(
        "/pdfs",
        files={"file": (filename, _build_fixture_pdf(), "application/pdf")},
    )


def _start_generation_job(
    client: TestClient, source_file: str = "book.pdf", additional_prompt: str = ""
):
    return client.post(
        "/generation-jobs",
        json={
            "sections": [
                {
                    "title": "01節 会計の意義",
                    "start_page": 1,
                    "end_page": None,
                    "deck_path": "Root::01節 会計の意義",
                    "source_file": source_file,
                }
            ],
            "additional_prompt": additional_prompt,
        },
    )


def _wait_until_complete(
    client: TestClient, job_id: str, timeout_seconds: float = 5.0
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/generation-jobs/{job_id}")
        body = response.json()
        if body["is_complete"]:
            return body
        time.sleep(0.05)
    raise AssertionError("generation job did not complete within the timeout")


class TestStartGenerationJob:
    def test_returns_a_job_id(self, client: TestClient) -> None:
        _upload_fixture_pdf(client)

        response = _start_generation_job(client)

        assert response.status_code == 200
        assert response.json()["job_id"]

    def test_display_end_page_converts_back_to_the_correct_extraction_range(
        self, client: TestClient
    ) -> None:
        # start_page=1, end_page=1 in the API's display semantics means
        # "just page 1" (inclusive). This must round-trip back to the
        # correct internal (exclusive) PageRange so extraction pulls in
        # exactly page 1's text and nothing from page 2.
        doc = fitz.open()
        page1 = doc.new_page(width=595, height=842)
        page1.insert_text((72, 72), "PAGE ONE CONTENT")
        page2 = doc.new_page(width=595, height=842)
        page2.insert_text((72, 72), "PAGE TWO CONTENT")
        pdf_bytes = doc.tobytes()
        doc.close()
        client.post(
            "/pdfs",
            files={"file": ("two_pages.pdf", pdf_bytes, "application/pdf")},
        )

        fake_ai_repository = _FakeAiRepository()
        app.dependency_overrides[get_ai_card_generator_repository] = (
            lambda: fake_ai_repository
        )

        start_response = client.post(
            "/generation-jobs",
            json={
                "sections": [
                    {
                        "title": "節1",
                        "start_page": 1,
                        "end_page": 1,
                        "deck_path": "Root::節1",
                        "source_file": "two_pages.pdf",
                    }
                ],
                "additional_prompt": "",
            },
        )
        job_id = start_response.json()["job_id"]
        _wait_until_complete(client, job_id)

        assert len(fake_ai_repository.calls) == 1
        section_text, _ = fake_ai_repository.calls[0]
        assert "PAGE ONE CONTENT" in section_text
        assert "PAGE TWO CONTENT" not in section_text

    def test_invalid_deck_path_returns_422(self, client: TestClient) -> None:
        _upload_fixture_pdf(client)

        response = client.post(
            "/generation-jobs",
            json={
                "sections": [
                    {
                        "title": "01節 会計の意義",
                        "start_page": 1,
                        "end_page": None,
                        "deck_path": "",
                        "source_file": "book.pdf",
                    }
                ],
                "additional_prompt": "",
            },
        )

        assert response.status_code == 422


class TestGetGenerationJobStatus:
    def test_polling_reaches_done_with_generated_cards(
        self, client: TestClient
    ) -> None:
        _upload_fixture_pdf(client)
        start_response = _start_generation_job(client)
        job_id = start_response.json()["job_id"]

        body = _wait_until_complete(client, job_id)

        assert body["job_id"] == job_id
        assert body["is_complete"] is True
        assert len(body["section_jobs"]) == 1
        assert body["section_jobs"][0]["status"] == "DONE"
        assert body["section_jobs"][0]["card_count"] == 1
        assert body["section_jobs"][0]["error_message"] is None

    def test_unknown_job_id_returns_404(self, client: TestClient) -> None:
        response = client.get("/generation-jobs/does-not-exist")

        assert response.status_code == 404


class TestDownloadGenerationJobPackage:
    def test_download_returns_apkg_bytes_with_attachment_headers(
        self, client: TestClient
    ) -> None:
        _upload_fixture_pdf(client)
        start_response = _start_generation_job(client)
        job_id = start_response.json()["job_id"]
        _wait_until_complete(client, job_id)

        response = client.get(f"/generation-jobs/{job_id}/download")

        assert response.status_code == 200
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="generated.apkg"'
        )
        assert len(response.content) > 0

    def test_unknown_job_id_returns_404(self, client: TestClient) -> None:
        response = client.get("/generation-jobs/does-not-exist/download")

        assert response.status_code == 404
