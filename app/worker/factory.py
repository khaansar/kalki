from app.ai.llm import OpenAiLlm
from app.clients.test_service import TestServiceClient
from app.config import Settings
from app.worker.budget import Budget
from app.worker.jobs import JobRunner


def build_runner(settings: Settings) -> JobRunner:
    budget = Budget(settings)
    return JobRunner(
        settings,
        TestServiceClient(settings, timeout=settings.blueprint_timeout_seconds),
        OpenAiLlm(settings, budget.record),
        budget,
    )
