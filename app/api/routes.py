from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import Companion, UserId, settings, verify_gateway
from app.api.schemas import (
    AnswerIn,
    AnswerOut,
    NextOut,
    OptionOut,
    PromptOut,
    SettingsIn,
    SettingsOut,
)
from app.db.models import Prompt, UserSettings

router = APIRouter(prefix="/companion-api", dependencies=[Depends(verify_gateway)])


def to_prompt_out(prompt: Prompt) -> PromptOut:
    question = prompt.question
    return PromptOut(
        id=prompt.id,
        question_text=question.question_text,
        options=[OptionOut(key=o["key"], text=o["text"]) for o in question.options],
    )


def to_settings_out(state: UserSettings) -> SettingsOut:
    return SettingsOut(
        hidden=state.hidden,
        sleeping_until=state.sleeping_until.replace(tzinfo=UTC) if state.sleeping_until else None,
        sleep_options_minutes=settings.sleep_options_minutes,
    )


@router.get("/next", response_model=NextOut, response_model_by_alias=True)
def next_prompt(user_id: UserId, companion: Companion) -> NextOut:
    prompt = companion.next_prompt(user_id)
    return NextOut(prompt=to_prompt_out(prompt) if prompt else None)


@router.post("/prompts/{prompt_id}/answer", response_model=AnswerOut)
def answer(prompt_id: UUID, body: AnswerIn, user_id: UserId, companion: Companion) -> AnswerOut:
    prompt = companion.answer(user_id, str(prompt_id), body.selected_option)
    return AnswerOut(
        correct=bool(prompt.is_correct),
        correct_option=prompt.question.correct_option,
        explanation=prompt.question.explanation,
    )


@router.post("/prompts/{prompt_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip(prompt_id: UUID, user_id: UserId, companion: Companion) -> Response:
    companion.skip(user_id, str(prompt_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings", response_model=SettingsOut)
def read_settings(user_id: UserId, companion: Companion) -> SettingsOut:
    return to_settings_out(companion.get_settings(user_id))


@router.put("/settings", response_model=SettingsOut)
def write_settings(body: SettingsIn, user_id: UserId, companion: Companion) -> SettingsOut:
    return to_settings_out(companion.update_settings(user_id, body.sleep_minutes, body.hidden))
