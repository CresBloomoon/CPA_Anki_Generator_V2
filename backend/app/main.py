from fastapi import FastAPI

app = FastAPI(title="CPA Anki Generator API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
