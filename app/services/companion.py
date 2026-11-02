import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.clients.attempt_service import AttemptServiceClient
from app.clients.base import ServiceUnavailable
from app.clients.payment_service import PaymentServiceClient
from app.clients.test_service import TestServiceClient
from app.config import Settings
from app.db import queries
from app.db.clock import utcnow
from app.db.models import Prompt, PromptStatus, UserSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NextResult:
    visible: bool
    prompt: Prompt | None = None


AWAY = NextResult(visible=False)
STROLLING = NextResult(visible=True)


class PromptNotFound(Exception):
    pass


class PromptClosed(Exception):
    pass


class TestRunning(Exception):
    pass


class InvalidChoice(Exception):
    pass


class CompanionService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        tests: TestServiceClient,
        attempts: AttemptServiceClient,
        payments: PaymentServiceClient,
    ) -> None:
        self._db = db
        self._settings = settings
        self._tests = tests
        self._attempts = attempts
        self._payments = payments

    def next_prompt(self, user_id: str) -> NextResult:
        if not self._rolled_out_to(user_id):
            return AWAY

        state = queries.get_user_settings(self._db, user_id)
        self._db.commit()
        if self._is_away(state):
            return AWAY

        try:
            if self._attempts.has_running_test(user_id):
                return AWAY
            if self._is_cooling_down(state):
                return STROLLING

            existing = queries.open_prompt(self._db, user_id)
            if existing:
                return NextResult(True, self._resume_or_expire(existing, state))

            test_ids = self._accessible_test_ids(user_id)
        except ServiceUnavailable as error:
            logger.warning("Staying hidden: %s", error)
            return AWAY

        if not test_ids:
            return STROLLING

        seen_since = utcnow() - timedelta(days=self._settings.seen_window_days)
        question = queries.pick_question(self._db, user_id, test_ids, seen_since)
        if question is None:
            return STROLLING

        prompt = Prompt(user_id=user_id, reframed_question_id=question.id, question=question)
        self._db.add(prompt)
        self._db.commit()
        return NextResult(True, prompt)

    def answer(self, user_id: str, prompt_id: str, selected_option: str) -> Prompt:
        prompt = self._open_owned_prompt(user_id, prompt_id)
        question = prompt.question
        if selected_option not in {option["key"] for option in question.options}:
            raise InvalidChoice

        if self._attempts.has_running_test(user_id):
            raise TestRunning

        is_correct = selected_option == question.correct_option
        if not queries.close_prompt(
            self._db, prompt.id, PromptStatus.ANSWERED, selected_option, is_correct
        ):
            raise PromptClosed

        state = queries.get_user_settings(self._db, user_id)
        state.skip_count = 0
        state.next_allowed_at = utcnow() + timedelta(minutes=self._settings.cooldown_minutes)
        self._db.commit()
        self._db.refresh(prompt)
        return prompt

    def skip(self, user_id: str, prompt_id: str) -> None:
        prompt = self._open_owned_prompt(user_id, prompt_id)
        if not queries.close_prompt(self._db, prompt.id, PromptStatus.SKIPPED):
            raise PromptClosed

        state = queries.get_user_settings(self._db, user_id)
        state.skip_count += 1
        wait = (
            self._settings.cooldown_minutes
            + self._settings.skip_extra_wait_minutes * state.skip_count
        )
        wait = min(wait, self._settings.max_wait_minutes)
        state.next_allowed_at = utcnow() + timedelta(minutes=wait)
        self._db.commit()

    def get_settings(self, user_id: str) -> UserSettings:
        state = queries.get_user_settings(self._db, user_id)
        self._db.commit()
        return state

    def update_settings(
        self, user_id: str, sleep_minutes: int | None, hidden: bool | None
    ) -> UserSettings:
        if sleep_minutes and sleep_minutes not in self._settings.sleep_options_minutes:
            raise InvalidChoice

        state = queries.get_user_settings(self._db, user_id)
        if hidden is not None:
            state.hidden = hidden
        if sleep_minutes == 0:
            state.sleeping_until = None
            state.next_allowed_at = None
        elif sleep_minutes:
            state.sleeping_until = utcnow() + timedelta(minutes=sleep_minutes)
            state.sleep_count += 1
        self._db.commit()
        return state

    def _rolled_out_to(self, user_id: str) -> bool:
        allowed = self._settings.allowed_user_ids
        return self._settings.enabled and (not allowed or user_id in allowed)

    def _is_away(self, state: UserSettings) -> bool:
        return state.hidden or (
            state.sleeping_until is not None and state.sleeping_until > utcnow()
        )

    def _is_cooling_down(self, state: UserSettings) -> bool:
        return state.next_allowed_at is not None and state.next_allowed_at > utcnow()

    def _accessible_test_ids(self, user_id: str) -> set[str]:
        free = set(self._tests.published_test_ids(free_only=True))
        finished = set(self._attempts.finished_test_ids(user_id))
        return free | self._payments.entitled_test_ids(user_id, sorted(finished - free))

    def _resume_or_expire(self, prompt: Prompt, state: UserSettings) -> Prompt | None:
        if self._is_live(prompt):
            return prompt
        queries.close_prompt(self._db, prompt.id, PromptStatus.EXPIRED)
        state.next_allowed_at = utcnow() + timedelta(minutes=self._settings.cooldown_minutes)
        self._db.commit()
        return None

    def _is_live(self, prompt: Prompt) -> bool:
        lifetime = timedelta(minutes=self._settings.prompt_ttl_minutes)
        return prompt.created_at + lifetime > utcnow()

    def _open_owned_prompt(self, user_id: str, prompt_id: str) -> Prompt:
        prompt = queries.owned_prompt(self._db, prompt_id, user_id)
        if prompt is None:
            raise PromptNotFound
        if prompt.status != PromptStatus.SHOWN or not self._is_live(prompt):
            raise PromptClosed
        return prompt
