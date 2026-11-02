from app.clients.test_service import TestServiceClient
from app.config import get_settings
from app.worker.jobs import enqueue_tests


def main() -> None:
    test_ids = TestServiceClient(get_settings()).published_test_ids()
    enqueue_tests(test_ids)
    print(f"Queued {len(test_ids)} tests")


if __name__ == "__main__":
    main()
