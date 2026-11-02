import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.clients.test_service import Question, Translation

MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


@dataclass(frozen=True)
class Candidate:
    question_id: str
    version: datetime
    text: str
    options: list[dict[str, str]]
    correct_option: str
    explanation: str | None


def parse_options(options_json: str | None) -> list[dict[str, str]]:
    try:
        parsed = json.loads(options_json or "")
    except ValueError:
        return []
    if isinstance(parsed, dict):
        return [{"key": str(key), "text": str(text)} for key, text in parsed.items()]
    if isinstance(parsed, list):
        return [
            {"key": str(item["id"]), "text": str(item["text"])}
            for item in parsed
            if isinstance(item, dict) and "id" in item and "text" in item
        ]
    return []


def question_version(question: Question, translation: Translation) -> datetime:
    return max(question.updated_at, translation.updated_at or question.updated_at)


def english_translation(question: Question) -> Translation | None:
    for translation in question.translations:
        if translation.language.lower().startswith("en"):
            return translation
    return None


def has_images(translation: Translation, options: list[dict[str, str]]) -> bool:
    texts = [translation.question_text or "", *(option["text"] for option in options)]
    return (
        bool(translation.question_images)
        or any((translation.option_images or {}).values())
        or any(MARKDOWN_IMAGE.search(text) for text in texts)
    )


def to_candidate(question: Question) -> Candidate | None:
    translation = english_translation(question)
    if question.question_type != "MCQ" or question.deleted_at or translation is None:
        return None

    options = parse_options(translation.options_json)
    correct_option = (question.correct_answer or {}).get("key")
    if (
        not (translation.question_text or "").strip()
        or len(options) < 2
        or correct_option not in {option["key"] for option in options}
        or has_images(translation, options)
    ):
        return None

    return Candidate(
        question_id=question.question_id,
        version=question_version(question, translation),
        text=translation.question_text,
        options=options,
        correct_option=correct_option,
        explanation=None if question.explanation_images else question.explanation,
    )
