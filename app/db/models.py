from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.clock import utcnow

Timestamp = DATETIME(fsp=6)


def new_id() -> str:
    return str(uuid4())


class QuestionStatus(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class PromptStatus(StrEnum):
    SHOWN = "SHOWN"
    ANSWERED = "ANSWERED"
    SKIPPED = "SKIPPED"
    EXPIRED = "EXPIRED"


class Base(DeclarativeBase):
    pass


class ReframedQuestion(Base):
    __tablename__ = "reframed_questions"
    __table_args__ = (
        UniqueConstraint("test_id", "question_id", "question_updated_at", name="uq_question_ver"),
        Index("ix_reframed_status_test", "status", "test_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(String(36))
    question_updated_at: Mapped[datetime] = mapped_column(Timestamp)
    test_id: Mapped[str] = mapped_column(String(36))
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    correct_option: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)


class ReframeJob(Base):
    __tablename__ = "reframe_jobs"
    __table_args__ = (
        UniqueConstraint("test_id", "run_date", name="uq_job_test_day"),
        Index("ix_job_claim", "status", "available_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(String(36))
    run_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow, onupdate=utcnow)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (
        Index("ix_prompt_user_status", "user_id", "status"),
        Index("ix_prompt_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64))
    reframed_question_id: Mapped[str] = mapped_column(ForeignKey("reframed_questions.id"))
    status: Mapped[str] = mapped_column(String(16), default=PromptStatus.SHOWN)
    selected_option: Mapped[str | None] = mapped_column(String(64))
    is_correct: Mapped[bool | None]
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(Timestamp)

    question: Mapped[ReframedQuestion] = relationship(lazy="joined")


class UserSettings(Base):
    __tablename__ = "settings"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hidden: Mapped[bool] = mapped_column(default=False)
    sleeping_until: Mapped[datetime | None] = mapped_column(Timestamp)
    next_allowed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    skip_count: Mapped[int] = mapped_column(default=0)
    sleep_count: Mapped[int] = mapped_column(default=0)


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(0))
