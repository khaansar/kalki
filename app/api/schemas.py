from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class OptionOut(ApiModel):
    key: str
    text: str


class PromptOut(ApiModel):
    id: str
    question_text: str
    options: list[OptionOut]


class NextOut(ApiModel):
    prompt: PromptOut | None


class AnswerIn(ApiModel):
    selected_option: str = Field(min_length=1, max_length=64)


class AnswerOut(ApiModel):
    correct: bool
    correct_option: str
    explanation: str | None


class SettingsIn(ApiModel):
    sleep_minutes: int | None = Field(default=None, ge=0)
    hidden: bool | None = None


class SettingsOut(ApiModel):
    hidden: bool
    sleeping_until: datetime | None
    sleep_options_minutes: list[int]
