from collections.abc import Collection
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from app.db.clock import utcnow
from app.db.models import (
    JobStatus,
    LlmUsage,
    ProcessedEvent,
    Prompt,
    PromptStatus,
    QuestionStatus,
    ReframedQuestion,
    ReframeJob,
    UserSettings,
)


def get_user_settings(db: Session, user_id: str) -> UserSettings:
    db.execute(insert(UserSettings).values(user_id=user_id).prefix_with("IGNORE"))
    return db.get_one(UserSettings, user_id)


def open_prompt(db: Session, user_id: str) -> Prompt | None:
    return db.scalar(
        select(Prompt)
        .where(Prompt.user_id == user_id, Prompt.status == PromptStatus.SHOWN)
        .order_by(Prompt.created_at.desc())
        .limit(1)
    )


def owned_prompt(db: Session, prompt_id: str, user_id: str) -> Prompt | None:
    return db.scalar(select(Prompt).where(Prompt.id == prompt_id, Prompt.user_id == user_id))


def close_prompt(
    db: Session,
    prompt_id: str,
    status: PromptStatus,
    selected_option: str | None = None,
    is_correct: bool | None = None,
) -> bool:
    result = db.execute(
        update(Prompt)
        .where(Prompt.id == prompt_id, Prompt.status == PromptStatus.SHOWN)
        .values(
            status=status,
            selected_option=selected_option,
            is_correct=is_correct,
            responded_at=utcnow(),
        )
    )
    return result.rowcount == 1


def pick_question(
    db: Session, user_id: str, test_ids: Collection[str], seen_since: datetime
) -> ReframedQuestion | None:
    seen = (
        select(ReframedQuestion.question_id)
        .join(Prompt, Prompt.reframed_question_id == ReframedQuestion.id)
        .where(Prompt.user_id == user_id, Prompt.created_at >= seen_since)
    )
    return db.scalar(
        select(ReframedQuestion)
        .where(
            ReframedQuestion.status == QuestionStatus.VERIFIED,
            ReframedQuestion.test_id.in_(test_ids),
            ReframedQuestion.question_id.not_in(seen),
        )
        .order_by(func.rand())
        .limit(1)
    )


def question_handled(db: Session, test_id: str, question_id: str, version: datetime) -> bool:
    return (
        db.scalar(
            select(ReframedQuestion.id).where(
                ReframedQuestion.test_id == test_id,
                ReframedQuestion.question_id == question_id,
                ReframedQuestion.question_updated_at == version,
            )
        )
        is not None
    )


def retire_outdated(db: Session, test_id: str, current: dict[str, datetime]) -> int:
    rows = db.scalars(
        select(ReframedQuestion).where(
            ReframedQuestion.test_id == test_id,
            ReframedQuestion.status == QuestionStatus.VERIFIED,
        )
    ).all()
    outdated = [r for r in rows if current.get(r.question_id) != r.question_updated_at]
    for row in outdated:
        row.status = QuestionStatus.RETIRED
    return len(outdated)


def enqueue_test(db: Session, test_id: str, run_date: date) -> None:
    db.execute(
        insert(ReframeJob)
        .values(
            test_id=test_id,
            run_date=run_date,
            status=JobStatus.PENDING,
            attempts=0,
            available_at=utcnow(),
        )
        .prefix_with("IGNORE")
    )


def mark_event_processed(db: Session, event_id: str) -> bool:
    result = db.execute(
        insert(ProcessedEvent)
        .values(event_id=event_id, processed_at=utcnow())
        .prefix_with("IGNORE")
    )
    return result.rowcount == 1


def claim_job(db: Session) -> ReframeJob | None:
    job = db.scalar(
        select(ReframeJob)
        .where(ReframeJob.status == JobStatus.PENDING, ReframeJob.available_at <= utcnow())
        .order_by(ReframeJob.id)
        .limit(1)
        .with_for_update()
    )
    if job:
        job.status = JobStatus.RUNNING
        job.attempts += 1
    return job


def requeue_running_jobs(db: Session) -> None:
    db.execute(
        update(ReframeJob)
        .where(ReframeJob.status == JobStatus.RUNNING)
        .values(status=JobStatus.PENDING)
    )


def finish_job(db: Session, job_id: int, status: JobStatus, error: str | None = None) -> None:
    db.execute(
        update(ReframeJob).where(ReframeJob.id == job_id).values(status=status, last_error=error)
    )


def retry_job(db: Session, job_id: int, error: str | None, delay_minutes: int) -> None:
    db.execute(
        update(ReframeJob)
        .where(ReframeJob.id == job_id)
        .values(
            status=JobStatus.PENDING,
            last_error=error,
            available_at=utcnow() + timedelta(minutes=delay_minutes),
        )
    )


def release_job(db: Session, job_id: int) -> None:
    db.execute(
        update(ReframeJob)
        .where(ReframeJob.id == job_id)
        .values(status=JobStatus.PENDING, attempts=ReframeJob.attempts - 1)
    )


def add_llm_usage(
    db: Session, day: date, input_tokens: int, output_tokens: int, cost_usd: Decimal
) -> None:
    statement = insert(LlmUsage).values(
        day=day, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd
    )
    db.execute(
        statement.on_duplicate_key_update(
            input_tokens=LlmUsage.input_tokens + statement.inserted.input_tokens,
            output_tokens=LlmUsage.output_tokens + statement.inserted.output_tokens,
            cost_usd=LlmUsage.cost_usd + statement.inserted.cost_usd,
        )
    )


def spend_on(db: Session, day: date) -> Decimal:
    return db.scalar(select(LlmUsage.cost_usd).where(LlmUsage.day == day)) or Decimal(0)
