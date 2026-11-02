import logging

from fastapi import FastAPI

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

get_settings()

app = FastAPI(title="Kalki", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
