from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass


class PdfNotFoundError(Exception):
    """Raised when no PDF is stored under the given source_file."""


class PdfContentMismatchError(Exception):
    """Raised when source_file already holds different bytes.

    Re-uploading the same source_file with genuinely different content
    used to silently overwrite the earlier bytes -- e.g. two different
    books that happen to share a filename would clobber each other with
    no warning. Since the app has no way to guess whether that was
    intentional, this is surfaced as an explicit error instead (see
    Phase4-9's dev-log).
    """


@dataclass(frozen=True)
class StoredPdf:
    pdf_bytes: bytes
    content_hash: str


class PdfStore:
    """In-memory storage for uploaded PDF bytes, keyed by source_file.

    No persistence: uploaded PDFs are lost on backend restart. This mirrors
    the legacy app's st.session_state.pdf_info, letting the scan and
    generation flows reference the same uploaded bytes by filename without
    requiring the user to re-upload.
    """

    def __init__(self) -> None:
        self._pdfs: dict[str, StoredPdf] = {}
        self._lock = threading.Lock()

    def save(self, source_file: str, pdf_bytes: bytes) -> None:
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()
        with self._lock:
            existing = self._pdfs.get(source_file)
            if existing is not None and existing.content_hash != content_hash:
                raise PdfContentMismatchError(
                    f"source_file {source_file!r} is already stored with "
                    "different content"
                )
            self._pdfs[source_file] = StoredPdf(
                pdf_bytes=pdf_bytes, content_hash=content_hash
            )

    def get(self, source_file: str) -> bytes:
        return self._get_stored(source_file).pdf_bytes

    def get_content_hash(self, source_file: str) -> str:
        # Used by StartGenerationJobUsecase to build the idempotency key
        # (see Phase4-9's dev-log) without needing to re-hash the full PDF
        # bytes itself.
        return self._get_stored(source_file).content_hash

    def _get_stored(self, source_file: str) -> StoredPdf:
        with self._lock:
            try:
                return self._pdfs[source_file]
            except KeyError:
                raise PdfNotFoundError(
                    f"no PDF stored for source_file {source_file!r}"
                ) from None
