from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.clients.base import ServiceClient, ServiceUnavailable, service_url
from app.config import Settings


class BlueprintModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="ignore")


class Translation(BlueprintModel):
    language: str
    question_text: str | None = None
    options_json: str | None = None
    question_images: list[dict] | None = None
    option_images: dict[str, list[dict]] | None = None
    updated_at: datetime | None = None


class Question(BlueprintModel):
    question_id: str
    question_type: str
    translations: list[Translation] = []
    correct_answer: dict | None = None
    explanation: str | None = None
    explanation_images: list[dict] | None = None
    updated_at: datetime
    deleted_at: datetime | None = None


class Section(BlueprintModel):
    questions: list[Question] = []


class Blueprint(BlueprintModel):
    test_id: str
    sections: list[Section] = []


class TestServiceClient(ServiceClient):
    def __init__(self, settings: Settings, timeout: float | None = None) -> None:
        super().__init__(
            service_url(settings.test_service_url, "/tests-api"),
            settings,
            timeout or settings.live_request_timeout_seconds,
        )

    def published_test_ids(self, free_only: bool = False) -> list[str]:
        params = {"free": "true"} if free_only else None
        return self.request("GET", "/internal/tests/published", params=params)

    def blueprint(self, test_id: str) -> Blueprint:
        body = self.request("GET", f"/internal/mock-tests/{test_id}/blueprint")
        try:
            return Blueprint.model_validate(body["data"])
        except (KeyError, ValidationError) as error:
            raise ServiceUnavailable(f"blueprint {test_id}: {error}") from error
