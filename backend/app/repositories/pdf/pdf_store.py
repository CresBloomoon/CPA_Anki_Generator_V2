from __future__ import annotations

import threading


class PdfNotFoundError(Exception):
    """Raised when no PDF is stored under the given source_file."""


class PdfStore:
    """In-memory storage for uploaded PDF bytes, keyed by source_file.

    No persistence: uploaded PDFs are lost on backend restart. This mirrors
    the legacy app's st.session_state.pdf_info, letting the scan and
    generation flows reference the same uploaded bytes by filename without
    requiring the user to re-upload.
    """

    def __init__(self) -> None:
        self._pdfs: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def save(self, source_file: str, pdf_bytes: bytes) -> None:
        with self._lock:
            self._pdfs[source_file] = pdf_bytes

    def get(self, source_file: str) -> bytes:
        with self._lock:
            try:
                return self._pdfs[source_file]
            except KeyError:
                raise PdfNotFoundError(
                    f"no PDF stored for source_file {source_file!r}"
                ) from None
