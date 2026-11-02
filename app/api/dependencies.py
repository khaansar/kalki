import hmac
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.clients.attempt_service import AttemptServiceClient
from app.clients.payment_service import PaymentServiceClient
from app.clients.test_service import TestServiceClient
from app.config import get_settings
from app.db.session import SessionLocal
from app.services.companion import CompanionService

settings = get_settings()
test_client = TestServiceClient(settings)
attempt_client = AttemptServiceClient(settings)
payment_client = PaymentServiceClient(settings)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def verify_gateway(
    caller: Annotated[str | None, Header(alias="X-Service-Caller")] = None,
    secret: Annotated[str | None, Header(alias="X-Service-Auth")] = None,
) -> None:
    expected = settings.gateway_secret.get_secret_value().encode()
    if caller != "api-gateway" or not hmac.compare_digest((secret or "").encode(), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Service authentication failed")


def current_user(user_id: Annotated[str | None, Header(alias="X-User-Id")] = None) -> str:
    try:
        return str(UUID(user_id or ""))
    except ValueError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required") from error


def get_companion(db: Annotated[Session, Depends(get_db)]) -> CompanionService:
    return CompanionService(db, settings, test_client, attempt_client, payment_client)


UserId = Annotated[str, Depends(current_user)]
Companion = Annotated[CompanionService, Depends(get_companion)]
