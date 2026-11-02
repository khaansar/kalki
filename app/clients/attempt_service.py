from app.clients.base import ServiceClient, service_url
from app.config import Settings


class AttemptServiceClient(ServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            service_url(settings.attempt_service_url, "/attempts-api"),
            settings,
            settings.live_request_timeout_seconds,
        )

    def has_running_test(self, user_id: str) -> bool:
        body = self.request("GET", f"/internal/attempts/users/{user_id}/active")
        return bool(body["data"]["active"])

    def finished_test_ids(self, user_id: str) -> list[str]:
        return self.request("GET", f"/internal/attempts/users/{user_id}/tests")["data"]
