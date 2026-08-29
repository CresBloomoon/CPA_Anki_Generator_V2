import hashlib

import pytest

from app.repositories.pdf.pdf_store import (
    PdfContentMismatchError,
    PdfNotFoundError,
    PdfStore,
)


class TestPdfStore:
    def test_save_then_get_round_trips(self) -> None:
        store = PdfStore()
        store.save("book.pdf", b"pdf-bytes")

        assert store.get("book.pdf") == b"pdf-bytes"

    def test_get_missing_source_file_raises(self) -> None:
        store = PdfStore()

        with pytest.raises(PdfNotFoundError):
            store.get("missing.pdf")

    def test_resaving_the_same_source_file_with_identical_content_succeeds(
        self,
    ) -> None:
        # Harmless no-op: re-uploading the exact same file (e.g. the user
        # accidentally re-selects it) must not be treated as a conflict.
        store = PdfStore()
        store.save("book.pdf", b"pdf-bytes")
        store.save("book.pdf", b"pdf-bytes")

        assert store.get("book.pdf") == b"pdf-bytes"

    def test_resaving_the_same_source_file_with_different_content_raises(
        self,
    ) -> None:
        # Two different books that happen to share a filename must not
        # silently clobber each other -- see Phase4-9's dev-log.
        store = PdfStore()
        store.save("book.pdf", b"first")

        with pytest.raises(PdfContentMismatchError):
            store.save("book.pdf", b"second")

        # The original content must survive the rejected overwrite attempt.
        assert store.get("book.pdf") == b"first"

    def test_different_source_files_are_stored_independently(self) -> None:
        store = PdfStore()
        store.save("book1.pdf", b"one")
        store.save("book2.pdf", b"two")

        assert store.get("book1.pdf") == b"one"
        assert store.get("book2.pdf") == b"two"

    def test_get_content_hash_returns_the_sha256_hex_digest(self) -> None:
        store = PdfStore()
        store.save("book.pdf", b"pdf-bytes")

        assert store.get_content_hash("book.pdf") == hashlib.sha256(
            b"pdf-bytes"
        ).hexdigest()

    def test_get_content_hash_missing_source_file_raises(self) -> None:
        store = PdfStore()

        with pytest.raises(PdfNotFoundError):
            store.get_content_hash("missing.pdf")
