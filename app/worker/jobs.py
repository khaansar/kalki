import logging
from threading import Event

from app.ai.filters import Candidate, to_candidate
from app.ai.llm import Llm
from app.ai.pipeline import rewrite_and_verify
from app.clients.test_service import TestServiceClient
from app.config import Settings
from app.db import queries
from app.db.clock import utcnow
from app.db.models import JobStatus, QuestionStatus, ReframedQuestion
from app.db.session import SessionLocal
from app.worker.budget import Budget, BudgetExceeded

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(
        self, settings: Settings, tests: TestServiceClient, llm: Llm, budget: Budget
    ) -> None:
        self._settings = settings
        self._tests = tests
        self._llm = llm
        self._budget = budget
        self._last_free_run = None

    def run(self, stop: Event) -> None:
        with SessionLocal() as db:
            queries.requeue_running_jobs(db)
            db.commit()

        while not stop.is_set():
            try:
                self._queue_free_tests()
                if not self.run_next_job():
                    stop.wait(self._settings.worker_poll_seconds)
            except Exception:
                logger.exception("Worker loop failed")
                stop.wait(self._settings.worker_poll_seconds)

    def run_next_job(self) -> bool:
        if self._budget.is_spent():
            return False

        with SessionLocal() as db:
            job = queries.claim_job(db)
            db.commit()
        if job is None:
            return False

        try:
            self.process_test(job.test_id)
        except BudgetExceeded:
            logger.info("Daily spending limit reached; test %s will resume", job.test_id)
            with SessionLocal() as db:
                queries.release_job(db, job.id)
                db.commit()
        except Exception as error:
            logger.exception("Job %s failed", job.id)
            self._record_failure(job.id, job.attempts, str(error))
        else:
            with SessionLocal() as db:
                queries.finish_job(db, job.id, JobStatus.DONE)
                db.commit()
        return True

    def process_test(self, test_id: str) -> None:
        blueprint = self._tests.blueprint(test_id)
        questions = {
            question.question_id: candidate
            for section in blueprint.sections
            for question in section.questions
            if (candidate := to_candidate(question))
        }

        with SessionLocal() as db:
            current = {key: value.version for key, value in questions.items()}
            retired = queries.retire_outdated(db, test_id, current)
            db.commit()
        if retired:
            logger.info("Retired %s outdated rewrites for test %s", retired, test_id)

        for candidate in questions.values():
            self._process_question(test_id, candidate)

    def _process_question(self, test_id: str, candidate: Candidate) -> None:
        with SessionLocal() as db:
            handled = queries.question_handled(
                db, test_id, candidate.question_id, candidate.version
            )
        if handled:
            return

        self._budget.ensure_available()
        try:
            outcome = rewrite_and_verify(candidate, self._llm, self._settings)
        except Exception:
            logger.exception("Question %s failed; a later run retries", candidate.question_id)
            return

        with SessionLocal() as db:
            db.add(
                ReframedQuestion(
                    question_id=candidate.question_id,
                    question_updated_at=candidate.version,
                    test_id=test_id,
                    question_text=outcome.text,
                    options=outcome.options,
                    correct_option=candidate.correct_option,
                    explanation=candidate.explanation,
                    status=QuestionStatus.VERIFIED if outcome.verified else QuestionStatus.REJECTED,
                    rejection_reason=outcome.reason,
                )
            )
            db.commit()

    def _queue_free_tests(self) -> None:
        now = utcnow()
        if self._last_free_run == now.date() or now.hour < self._settings.free_tests_run_hour_utc:
            return

        test_ids = self._tests.published_test_ids(free_only=True)
        enqueue_tests(test_ids)
        self._last_free_run = now.date()

    def _record_failure(self, job_id: int, attempts: int, error: str) -> None:
        with SessionLocal() as db:
            if attempts >= self._settings.job_max_attempts:
                queries.finish_job(db, job_id, JobStatus.FAILED, error)
            else:
                queries.retry_job(db, job_id, error, self._settings.job_retry_delay_minutes)
            db.commit()


def enqueue_tests(test_ids: list[str]) -> None:
    today = utcnow().date()
    with SessionLocal() as db:
        for test_id in test_ids:
            queries.enqueue_test(db, test_id, today)
        db.commit()
