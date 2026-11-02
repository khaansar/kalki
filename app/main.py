import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.clients.base import ServiceUnavailable
from app.services.companion import InvalidChoice, PromptClosed, PromptNotFound, TestRunning

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Kalki", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)

ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    PromptNotFound: (status.HTTP_404_NOT_FOUND, "Prompt not found"),
    PromptClosed: (status.HTTP_409_CONFLICT, "Prompt is no longer open"),
    TestRunning: (status.HTTP_409_CONFLICT, "A test is running"),
    InvalidChoice: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid choice"),
    ServiceUnavailable: (status.HTTP_503_SERVICE_UNAVAILABLE, "Try again later"),
}


def handle_error(_: Request, error: Exception) -> JSONResponse:
    status_code, message = ERROR_RESPONSES[type(error)]
    return JSONResponse(status_code=status_code, content={"message": message})


for error_type in ERROR_RESPONSES:
    app.add_exception_handler(error_type, handle_error)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
