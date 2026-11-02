from itertools import batched

from app.clients.base import ServiceClient, service_url
from app.config import Settings

CHECK_BATCH_LIMIT = 200


class PaymentServiceClient(ServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            service_url(settings.payment_service_url, "/payments-api"),
            settings,
            settings.live_request_timeout_seconds,
        )

    def entitled_test_ids(self, user_id: str, test_ids: list[str]) -> set[str]:
        entitled: set[str] = set()
        for group in batched(test_ids, CHECK_BATCH_LIMIT):
            body = self.request(
                "POST",
                "/internal/entitlements/check-batch",
                json={"userId": user_id, "testIds": list(group)},
            )
            entitled.update(test_id for test_id, allowed in body["data"].items() if allowed)
        return entitled
