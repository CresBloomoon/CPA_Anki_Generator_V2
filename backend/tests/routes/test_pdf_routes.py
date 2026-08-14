import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_pdf_store
from app.main import app
from app.repositories.pdf.pdf_store import PdfStore


@pytest.fixture()
def client():
    test_pdf_store = PdfStore()
    app.dependency_overrides[get_pdf_store] = lambda: test_pdf_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _build_fixture_pdf_with_toc() -> bytes:
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=595, height=842)
    doc.set_toc(
        [
            [1, "第01章 総論", 1],
            [2, "第01節 会計の意義", 2],
            [2, "第02節 会計公準", 3],
        ]
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestUploadPdf:
    def test_upload_returns_source_file_and_size(self, client: TestClient) -> None:
        pdf_bytes = _build_fixture_pdf_with_toc()

        response = client.post(
            "/pdfs",
            files={"file": ("book.pdf", pdf_bytes, "application/pdf")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["source_file"] == "book.pdf"
        assert body["size_bytes"] == len(pdf_bytes)


class TestScanPdfs:
    def test_scan_returns_sections_with_hierarchy_reflected_in_deck_path(
        self, client: TestClient
    ) -> None:
        pdf_bytes = _build_fixture_pdf_with_toc()
        client.post(
            "/pdfs", files={"file": ("book.pdf", pdf_bytes, "application/pdf")}
        )

        response = client.post(
            "/scan",
            json={
                "source_files": ["book.pdf"],
                "root_path": "公認会計士試験::財務会計論",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["warnings"] == []
        titles = [s["title"] for s in body["sections"]]
        assert titles == ["第01章 総論", "第01節 会計の意義", "第02節 会計公準"]

        section_titles = {s["title"]: s for s in body["sections"]}
        assert (
            section_titles["第01節 会計の意義"]["deck_path"]
            == "公認会計士試験::財務会計論::第01章 総論::第01節 会計の意義"
        )
        assert section_titles["第01節 会計の意義"]["source_file"] == "book.pdf"

    def test_scan_converts_end_page_to_the_inclusive_last_page_for_display(
        self, client: TestClient
    ) -> None:
        # PdfStructureRepository internally computes end_page as the *next*
        # section's start_page (exclusive -- see page_range_display.py).
        # /scan must convert this to the section's own last page (inclusive)
        # before it reaches the API, or adjacent sections appear to share a
        # boundary page in the UI.
        pdf_bytes = _build_fixture_pdf_with_toc()
        client.post(
            "/pdfs", files={"file": ("book.pdf", pdf_bytes, "application/pdf")}
        )

        response = client.post(
            "/scan",
            json={"source_files": ["book.pdf"], "root_path": "Root"},
        )

        section_titles = {s["title"]: s for s in response.json()["sections"]}
        # 第01章 spans only page 1 (第01節 begins on page 2).
        assert section_titles["第01章 総論"]["start_page"] == 1
        assert section_titles["第01章 総論"]["end_page"] == 1
        # 第01節 spans only page 2 (第02節 begins on page 3).
        assert section_titles["第01節 会計の意義"]["start_page"] == 2
        assert section_titles["第01節 会計の意義"]["end_page"] == 2
        # 第02節 is the last TOC entry -- open-ended, stays None.
        assert section_titles["第02節 会計公準"]["start_page"] == 3
        assert section_titles["第02節 会計公準"]["end_page"] is None

    def test_scan_unknown_source_file_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/scan",
            json={"source_files": ["missing.pdf"], "root_path": "Root"},
        )

        assert response.status_code == 404

    def test_scan_invalid_pdf_bytes_returns_422(self, client: TestClient) -> None:
        client.post(
            "/pdfs",
            files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
        )

        response = client.post(
            "/scan",
            json={"source_files": ["broken.pdf"], "root_path": "Root"},
        )

        assert response.status_code == 422


class TestUploadPdfValidation:
    def test_upload_without_filename_returns_400(self, client: TestClient) -> None:
        # httpxの files={} 簡易記法では filename="" を渡すと Content-Disposition
        # から filename 属性ごと省略されてしまい、Starlette側がファイルパートで
        # はなく通常の文字列フィールドとして解釈するため、FastAPI標準の422
        # （UploadFile型不一致エラー）が発生し自前バリデーションに到達できない。
        # 一方で実際のブラウザは <input type="file"> が未選択のままフォーム
        # 送信されると、filename 属性自体は残したまま値だけが空文字列の
        # パートを送信する（WHATWG HTML標準）。このテストではその実際の
        # ブラウザ挙動を再現するため、multipartボディを手組みして
        # filename="" を明示的に残した状態で送信する。
        boundary = "test-boundary-empty-filename"
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename=""\r\n'
            f'Content-Type: application/pdf\r\n'
            f'\r\n'
            f'pdf-bytes\r\n'
            f'--{boundary}--\r\n'
        ).encode("utf-8")

        response = client.post(
            "/pdfs",
            content=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

        assert response.status_code == 400
