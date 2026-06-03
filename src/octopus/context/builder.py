from datetime import UTC, datetime
from pathlib import Path

from octopus.context.file_scanner import scan_project_files
from octopus.context.markdown_sections import MarkdownSection, read_markdown_sections
from octopus.context.profiles import (
    DEFAULT_TOKEN_BUDGET,
    PROFILE_RULES,
    ContextProfile,
)
from octopus.context.token_estimator import estimate_tokens, get_token_status
from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    COMPUTE_BUDGET_MD,
    CURRENT_CONTEXT,
    DATA_STRATEGY_MD,
    EXPERIMENT_MD,
    ML_DESIGN_MD,
    REQUIREMENTS_MD,
    TASKS_MD,
)
from octopus.core.schemas import ContextBuildResult, ProjectState

PLAN_SECTIONS = [
    ("Requirements Summary", REQUIREMENTS_MD),
    ("ML Design Summary", ML_DESIGN_MD),
    ("Data Strategy", DATA_STRATEGY_MD),
    ("Experiment Plan", EXPERIMENT_MD),
    ("Compute Budget", COMPUTE_BUDGET_MD),
    ("Task List", TASKS_MD),
]


def _read_plan_file(path: Path) -> str:
    if not path.exists():
        return "_Not generated yet._"
    return path.read_text(encoding="utf-8").strip()


def _state_snapshot(state: ProjectState) -> str:
    lines = [
        "## Project Snapshot",
        "",
        f"- Project: {state.project_name or 'Unnamed Project'}",
        f"- Goal: {state.project_goal or 'not set'}",
        f"- Type: {state.task_type or state.project_type}",
        f"- Dataset: {state.dataset_status or 'unknown'}",
        f"- Main metric: {state.main_metric or 'not set'}",
        f"- Target score: {state.target_score if state.target_score is not None else 'not set'}",
        f"- GPU: {'yes' if state.compute.has_gpu else 'no'}",
    ]
    if state.compute.environment:
        lines.append(f"- Environment: {state.compute.environment}")
    return "\n".join(lines)


def _section_matches(title: str, keywords: tuple[str, ...]) -> bool:
    normalized = title.lower()
    return any(keyword in normalized for keyword in keywords)


def _task_relevance_bonus(task: str, section: MarkdownSection) -> int:
    words = {
        word.strip(".,:;()[]{}").lower()
        for word in task.split()
        if len(word.strip(".,:;()[]{}")) >= 4
    }
    if not words:
        return 0
    haystack = f"{section.title}\n{section.content}".lower()
    return -5 if any(word in haystack for word in words) else 0


def _format_section(path: Path, section: MarkdownSection) -> str:
    return f"<!-- source: {path.as_posix()}#{section.title} -->\n{section.content}"


def _select_profile_sections(
    task: str, profile: ContextProfile
) -> tuple[list[tuple[int, Path, MarkdownSection]], list[str]]:
    selected: list[tuple[int, Path, MarkdownSection]] = []
    skipped: list[str] = []
    seen: set[tuple[str, str]] = set()

    for rule in PROFILE_RULES[profile]:
        sections = read_markdown_sections(rule.path)
        if not sections:
            skipped.append(f"{rule.path.as_posix()} (missing)")
            continue
        for section in sections:
            key = (rule.path.as_posix(), section.title)
            if key in seen:
                continue
            if _section_matches(section.title, rule.title_keywords):
                seen.add(key)
                priority = rule.priority + _task_relevance_bonus(task, section)
                selected.append((priority, rule.path, section))

    selected.sort(key=lambda item: (item[0], item[1].as_posix(), item[2].title))
    return selected, skipped


def _all_plan_sections() -> tuple[list[tuple[int, Path, MarkdownSection]], list[str]]:
    selected: list[tuple[int, Path, MarkdownSection]] = []
    skipped: list[str] = []
    for priority, (_, path) in enumerate(PLAN_SECTIONS, start=1):
        sections = read_markdown_sections(path)
        if not sections:
            skipped.append(f"{path.as_posix()} (missing)")
            continue
        selected.extend((priority * 10, path, section) for section in sections)
    return selected, skipped


def build_context(
    state: ProjectState,
    task: str,
    *,
    profile: ContextProfile = "training",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    full: bool = False,
    write: bool = True,
) -> tuple[str, ContextBuildResult]:
    body = [
        f"# Current Context - {state.project_name or 'Unnamed Project'}",
        "",
        f"> Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"> Task: {task}",
        f"> Profile: {'full' if full else profile}",
        f"> Token budget: {'unbounded' if full else token_budget}",
        "> Estimated tokens: pending",
        "",
        "---",
        "",
        "## Current Task",
        "",
        task,
        "",
        _state_snapshot(state),
        "",
    ]

    selected, skipped_sections = (
        _all_plan_sections() if full else _select_profile_sections(task, profile)
    )
    included_plan_files: list[str] = []
    included_sections: list[str] = []
    context_blocks: list[str] = []
    current_content = "\n".join(body)

    for _, path, section in selected:
        block = _format_section(path, section)
        section_ref = f"{path.as_posix()}#{section.title}"
        if not full and estimate_tokens(f"{current_content}\n\n{block}") > token_budget:
            skipped_sections.append(f"{section_ref} (budget)")
            continue
        context_blocks.append(block)
        current_content = f"{current_content}\n\n{block}"
        included_sections.append(section_ref)
        path_name = path.as_posix()
        if path_name not in included_plan_files:
            included_plan_files.append(path_name)

    if context_blocks:
        body.extend(["## Selected Planning Context", ""])
        body.extend(context_blocks)
        body.append("")
    else:
        body.extend(
            ["## Selected Planning Context", "", "_No matching planning sections found._", ""]
        )

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
        profile="full" if full else profile,
        output_path=CURRENT_CONTEXT.as_posix(),
        estimated_tokens=token_count,
        token_status=get_token_status(token_count),
        included_files=included_plan_files,
        included_sections=included_sections,
        skipped_sections=skipped_sections,
        excluded_files=excluded_files,
        excluded_patterns=excluded_patterns,
    )
    if write:
        atomic_write_text(CURRENT_CONTEXT, content)
    return content, result
