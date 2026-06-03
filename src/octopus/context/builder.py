from datetime import UTC, datetime
from pathlib import Path

from octopus.context.file_scanner import scan_project_files
from octopus.context.token_estimator import estimate_tokens, get_token_status
from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    CURRENT_CONTEXT,
    EXPERIMENT_MD,
    ML_DESIGN_MD,
    REQUIREMENTS_MD,
    TASKS_MD,
)
from octopus.core.schemas import ContextBuildResult, ProjectState

PLAN_SECTIONS = [
    ("Requirements Summary", REQUIREMENTS_MD),
    ("ML Design Summary", ML_DESIGN_MD),
    ("Experiment Plan", EXPERIMENT_MD),
    ("Task List", TASKS_MD),
]


def _read_plan_file(path: Path) -> str:
    if not path.exists():
        return "_Not generated yet._"
    return path.read_text(encoding="utf-8").strip()


def build_context(
    state: ProjectState, task: str, *, write: bool = True
) -> tuple[str, ContextBuildResult]:
    body = [
        f"# Current Context - {state.project_name or 'Unnamed Project'}",
        "",
        f"> Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"> Task: {task}",
        "> Estimated tokens: pending",
        "",
        "---",
        "",
        "## Current Task",
        "",
        task,
        "",
    ]

    included_plan_files: list[str] = []
    for title, path in PLAN_SECTIONS:
        body.extend([f"## {title}", ""])
        body.append(_read_plan_file(path))
        body.append("")
        if path.exists():
            included_plan_files.append(path.as_posix())

    body.extend(
        [
            "## Constraints",
            "",
            "- Do not load raw datasets into context.",
            "- Do not modify architecture without ADR.",
            "",
            "## Expected Output",
            "",
            f"_Implement: {task}_",
            "",
        ]
    )
    content = "\n".join(body)
    token_count = estimate_tokens(content)
    content = content.replace("> Estimated tokens: pending", f"> Estimated tokens: {token_count}")

    _, excluded_files, excluded_patterns = scan_project_files()
    result = ContextBuildResult(
        task=task,
        output_path=CURRENT_CONTEXT.as_posix(),
        estimated_tokens=token_count,
        token_status=get_token_status(token_count),
        included_files=included_plan_files,
        excluded_files=excluded_files,
        excluded_patterns=excluded_patterns,
    )
    if write:
        atomic_write_text(CURRENT_CONTEXT, content)
    return content, result
