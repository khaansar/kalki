from collections.abc import Callable
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.ai.templates import render
from app.config import Settings


class OptionText(BaseModel):
    key: str
    text: str


class Rewrite(BaseModel):
    question_text: str
    options: list[OptionText] = Field(min_length=2)


class Solution(BaseModel):
    selected_option: str


class MeaningVerdict(BaseModel):
    same_meaning: bool
    reason: str


class LlmOutputError(Exception):
    pass


class Llm(Protocol):
    def rewrite(self, text: str, options: list[dict[str, str]]) -> Rewrite: ...

    def solve(self, text: str, options: list[dict[str, str]]) -> str: ...

    def same_meaning(
        self,
        original: tuple[str, list[dict[str, str]]],
        rewritten: tuple[str, list[dict[str, str]]],
    ) -> MeaningVerdict: ...


class OpenAiLlm:
    def __init__(self, settings: Settings, on_usage: Callable[[dict[str, Any]], None]) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for kalki-worker")
        self._model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=2,
        )
        self._on_usage = on_usage

    def rewrite(self, text: str, options: list[dict[str, str]]) -> Rewrite:
        return self._ask(Rewrite, "rewrite_system", render("question", text=text, options=options))

    def solve(self, text: str, options: list[dict[str, str]]) -> str:
        content = render("question", text=text, options=options)
        return self._ask(Solution, "solve_system", content).selected_option

    def same_meaning(
        self,
        original: tuple[str, list[dict[str, str]]],
        rewritten: tuple[str, list[dict[str, str]]],
    ) -> MeaningVerdict:
        content = f"Original: {format_question(*original)}\nRewrite: {format_question(*rewritten)}"
        return self._ask(MeaningVerdict, MEANING_PROMPT, content)

    def _ask[T: BaseModel](self, schema: type[T], system_template: str, content: str) -> T:
        structured = self._model.with_structured_output(schema, include_raw=True)
        result = structured.invoke([SystemMessage(render(system_template)), HumanMessage(content)])
        usage = result["raw"].usage_metadata
        if usage:
            self._on_usage(usage)
        if result["parsed"] is None:
            raise LlmOutputError(str(result["parsing_error"]))
        return result["parsed"]
