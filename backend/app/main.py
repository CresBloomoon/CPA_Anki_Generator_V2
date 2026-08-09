from fastapi import FastAPI

from app.routes.pdf_routes import router as pdf_router

app = FastAPI(title="CPA Anki Generator API")
app.include_router(pdf_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
