from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

import octopus
from octopus.core.schemas import ProjectState

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default_for_string=False, default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def template_context(state: ProjectState, **extra: Any) -> dict[str, Any]:
    context = state.model_dump(mode="json")
    context["octopus_version"] = octopus.__version__
    context["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    context.update(extra)
    return context


def render_template(template_name: str, state: ProjectState, **extra: Any) -> str:
    template = _environment().get_template(template_name)
    return template.render(**template_context(state, **extra))
