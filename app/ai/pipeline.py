from dataclasses import dataclass

from app.ai.checks import find_problem
from app.ai.filters import Candidate
from app.ai.llm import Llm
from app.config import Settings

SOLVE_RUNS = 2


@dataclass(frozen=True)
class Outcome:
    verified: bool
    text: str
    options: list[dict[str, str]]
    reason: str | None = None


def rewrite_and_verify(candidate: Candidate, llm: Llm, settings: Settings) -> Outcome:
    reason = None
    for _ in range(settings.rewrite_max_retries + 1):
        rewrite = llm.rewrite(candidate.text, candidate.options)
        rewritten = [{"key": option.key, "text": option.text} for option in rewrite.options]
        text = rewrite.question_text

        reason = find_problem(candidate, text, rewritten) or failed_ai_check(
            candidate, text, rewritten, llm
        )
        if reason is None:
            return Outcome(True, text, ordered_like(candidate, rewritten))

    return Outcome(False, text, rewritten, reason)


def ordered_like(candidate: Candidate, options: list[dict[str, str]]) -> list[dict[str, str]]:
    texts = {option["key"]: option["text"] for option in options}
    return [{"key": option["key"], "text": texts[option["key"]]} for option in candidate.options]


def failed_ai_check(
    candidate: Candidate, text: str, options: list[dict[str, str]], llm: Llm
) -> str | None:
    for _ in range(SOLVE_RUNS):
        if llm.solve(text, options) != candidate.correct_option:
            return "solver disagreed with the stored answer"

    verdict = llm.same_meaning((candidate.text, candidate.options), (text, options))
    return None if verdict.same_meaning else f"meaning changed: {verdict.reason}"
