import logging

from fastapi import FastAPI

from app.routes.generation_routes import router as generation_router
from app.routes.pdf_routes import router as pdf_router
from app.routes.settings_routes import router as settings_router

# Without this, app.* loggers' INFO/WARNING calls are silently dropped --
# the root logger defaults to WARNING with no handler, and uvicorn only
# configures its own "uvicorn"/"uvicorn.access"/"uvicorn.error" loggers,
# not arbitrary application loggers. This makes generation progress logs
# (see generate_cards_for_section_usecase.py, gemini_repository.py) show
# up in `docker compose logs backend`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="CPA Anki Generator API")
app.include_router(pdf_router)
app.include_router(generation_router)
app.include_router(settings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
