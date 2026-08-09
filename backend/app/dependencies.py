from __future__ import annotations

from app.repositories.pdf.pdf_store import PdfStore

# Process-wide singletons. No persistence: state is lost on backend
# restart, which is an accepted trade-off for a single-user, Docker
# Compose-only deployment (see JobStore/PdfStore docstrings).
pdf_store = PdfStore()


def get_pdf_store() -> PdfStore:
    return pdf_store
