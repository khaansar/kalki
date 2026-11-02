from typing import Any

import httpx

from app.config import Settings


def service_url(base_url: str, context_path: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith(context_path) else f"{base}{context_path}"


class ServiceUnavailable(Exception):
    pass


class ServiceClient:
    def __init__(self, base_url: str, settings: Settings, timeout: float) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "X-Service-Caller": "kalki",
                "X-Service-Auth": settings.service_secret.get_secret_value(),
            },
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ServiceUnavailable(f"{method} {path}: {error}") from error
