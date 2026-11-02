import re
from collections import Counter

from app.ai.filters import Candidate

NUMBER = re.compile(r"\d+(?:\.\d+)?")
UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$")
BEGIN_ENV = re.compile(r"\\begin\{(\w+\*?)\}")
END_ENV = re.compile(r"\\end\{(\w+\*?)\}")


def numbers_in(text: str) -> Counter[str]:
    return Counter(NUMBER.findall(text))


def has_valid_latex(text: str) -> bool:
    depth = 0
    previous = ""
    for character in text:
        if previous != "\\":
            depth += (character == "{") - (character == "}")
        if depth < 0:
            return False
        previous = "" if previous == "\\" else character
    return (
        depth == 0
        and len(UNESCAPED_DOLLAR.findall(text)) % 2 == 0
        and Counter(BEGIN_ENV.findall(text)) == Counter(END_ENV.findall(text))
    )


def find_problem(candidate: Candidate, text: str, options: list[dict[str, str]]) -> str | None:
    original = {option["key"]: option["text"] for option in candidate.options}
    rewritten = {option["key"]: option["text"] for option in options}

    if len(options) != len(rewritten) or original.keys() != rewritten.keys():
        return "option keys changed"
    if not text.strip() or not all(value.strip() for value in rewritten.values()):
        return "empty text"
    if numbers_in(candidate.text) != numbers_in(text):
        return "question numbers changed"
    if any(numbers_in(original[key]) != numbers_in(rewritten[key]) for key in original):
        return "option numbers changed"
    if not all(has_valid_latex(value) for value in (text, *rewritten.values())):
        return "invalid LaTeX"
    return None
