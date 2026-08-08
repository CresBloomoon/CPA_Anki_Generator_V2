import pytest

from app.repositories.pdf.pdf_store import PdfNotFoundError, PdfStore


class TestPdfStore:
    def test_save_then_get_round_trips(self) -> None:
        store = PdfStore()
        store.save("book.pdf", b"pdf-bytes")

        assert store.get("book.pdf") == b"pdf-bytes"

    def test_get_missing_source_file_raises(self) -> None:
        store = PdfStore()

        with pytest.raises(PdfNotFoundError):
            store.get("missing.pdf")

    def test_save_overwrites_existing_entry_for_the_same_source_file(self) -> None:
        store = PdfStore()
        store.save("book.pdf", b"first")
        store.save("book.pdf", b"second")

        assert store.get("book.pdf") == b"second"

    def test_different_source_files_are_stored_independently(self) -> None:
        store = PdfStore()
        store.save("book1.pdf", b"one")
        store.save("book2.pdf", b"two")

        assert store.get("book1.pdf") == b"one"
        assert store.get("book2.pdf") == b"two"
