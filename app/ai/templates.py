from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

environment = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "prompts"),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=False,
)


def render(name: str, **context: Any) -> str:
    return environment.get_template(f"{name}.j2").render(**context).strip()
