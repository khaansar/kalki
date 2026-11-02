import json
from decimal import Decimal

from sqlalchemy import func, select

from app.db.models import LlmUsage, Prompt, QuestionStatus, ReframedQuestion, UserSettings
from app.db.session import SessionLocal


def collect() -> dict[str, float | int | None]:
    with SessionLocal() as db:
        questions = dict(
            db.execute(
                select(ReframedQuestion.status, func.count()).group_by(ReframedQuestion.status)
            ).all()
        )
        prompts = dict(
            db.execute(select(Prompt.status, func.count()).group_by(Prompt.status)).all()
        )
        slept = db.scalar(select(func.coalesce(func.sum(UserSettings.sleep_count), 0)))
        spent = db.scalar(select(func.coalesce(func.sum(LlmUsage.cost_usd), 0)))

    rejected = questions.get(QuestionStatus.REJECTED, 0)
    verified = questions.get(QuestionStatus.VERIFIED, 0) + questions.get(QuestionStatus.RETIRED, 0)
    reviewed = verified + rejected
    return {
        "verification_pass_rate": round(verified / reviewed, 4) if reviewed else None,
        "answered": prompts.get("ANSWERED", 0),
        "skipped": prompts.get("SKIPPED", 0),
        "expired": prompts.get("EXPIRED", 0),
        "slept": int(slept),
        "total_cost_usd": float(spent),
        "cost_per_verified_question_usd": (float(Decimal(spent) / verified) if verified else None),
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
