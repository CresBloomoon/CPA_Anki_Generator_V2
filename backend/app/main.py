from fastapi import FastAPI

from app.routes.generation_routes import router as generation_router
from app.routes.pdf_routes import router as pdf_router

app = FastAPI(title="CPA Anki Generator API")
app.include_router(pdf_router)
app.include_router(generation_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
