from decimal import Decimal
from typing import Any

from app.config import Settings
from app.db import queries
from app.db.clock import utcnow
from app.db.session import SessionLocal

TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self, settings: Settings) -> None:
        self._limit = Decimal(str(settings.daily_spend_limit_usd))
        self._input_price = Decimal(str(settings.openai_input_usd_per_million))
        self._output_price = Decimal(str(settings.openai_output_usd_per_million))

    def is_spent(self) -> bool:
        with SessionLocal() as db:
            return queries.spend_on(db, utcnow().date()) >= self._limit

    def ensure_available(self) -> None:
        if self.is_spent():
            raise BudgetExceeded

    def record(self, usage: dict[str, Any]) -> None:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = (
            input_tokens * self._input_price + output_tokens * self._output_price
        ) / TOKENS_PER_PRICE_UNIT
        with SessionLocal() as db:
            queries.add_llm_usage(db, utcnow().date(), input_tokens, output_tokens, cost)
            db.commit()
