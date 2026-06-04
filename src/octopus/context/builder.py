import re
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
    BEST_RUNS_MD,
    COMPUTE_BUDGET_MD,
    CURRENT_CONTEXT,
    DATA_STRATEGY_MD,
    EXPERIMENT_MD,
    EXPERIMENT_MEMORY_MD,
    ML_DESIGN_MD,
    NEXT_STEPS_MD,
    REQUIREMENTS_MD,
    SELECTED_DIRECTION_YAML,
    TASKS_MD,
)
from octopus.core.schemas import ContextBuildResult, NextDirection, ProjectState
from octopus.experiments.selection import get_direction

PLAN_SECTIONS = [
    ("Requirements Summary", REQUIREMENTS_MD),
    ("Machine Learning Design Summary", ML_DESIGN_MD),
    ("Data Strategy", DATA_STRATEGY_MD),
    ("Experiment Plan", EXPERIMENT_MD),
    ("Compute Budget", COMPUTE_BUDGET_MD),
    ("Task List", TASKS_MD),
]
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".toml", ".yaml", ".yml", ".sh"}
CODE_HINTS = (
    "train",
    "training",
    "baseline",
    "model",
    "data",
    "dataset",
    "loader",
    "eval",
    "metric",
    "config",
    "loss",
)
GENERATED_CONTEXT_FILES = {
    REQUIREMENTS_MD.as_posix(),
    ML_DESIGN_MD.as_posix(),
    DATA_STRATEGY_MD.as_posix(),
    EXPERIMENT_MD.as_posix(),
    COMPUTE_BUDGET_MD.as_posix(),
    TASKS_MD.as_posix(),
    CURRENT_CONTEXT.as_posix(),
}
DIRECTION_KEYWORDS = {
    "class_imbalance": [
        "loss",
        "class_weight",
        "sampler",
        "weighted",
        "dataset",
        "collate",
        "label",
        "metrics",
    ],
    "augmentation": ["augment", "preprocess", "transform", "dataset", "tokenizer"],
    "metric": ["evaluate", "metrics", "classification_report", "confusion", "score"],
    "learning_rate": ["optimizer", "scheduler", "lr", "warmup", "config", "train"],
    "rag_retrieval": ["retriever", "embedding", "chunk", "index", "vector", "bm25", "qdrant"],
}


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
        f"- Selected baseline: {state.baseline_model or 'default for task type'}",
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


def _task_words(task: str) -> set[str]:
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z0-9_+-]+", task)
        if len(word) >= 3
    }


def _language_for_path(path: Path) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".sql": "sql",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sh": "bash",
    }.get(path.suffix.lower(), "text")


def _code_file_score(path: Path, text: str, task: str) -> int:
    rel = path.as_posix().lower()
    task_words = _task_words(task)
    score = 0
    for word in task_words:
        if word in rel:
            score += 8
        if word in text[:8_000].lower():
            score += 3
    for hint in CODE_HINTS:
        if hint in rel:
            score += 5
        if hint in text[:8_000].lower():
            score += 1
    if ("test" in rel or rel.startswith("tests/")) and not any(
        word in task.lower() for word in ("test", "debug", "review")
    ):
        score -= 6
    return score


def _snippet_for_file(path: Path, task: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if len(lines) <= 90:
        return text.strip()

    keywords = _task_words(task) | set(CODE_HINTS)
    selected: list[int] = []
    for index, line in enumerate(lines):
        haystack = line.lower()
        if any(keyword in haystack for keyword in keywords):
            selected.extend(range(max(0, index - 2), min(len(lines), index + 3)))
        if len(set(selected)) >= 90:
            break
    if not selected:
        selected = list(range(min(len(lines), 80)))

    snippet_lines: list[str] = []
    previous = -1
    for index in sorted(set(selected))[:90]:
        if previous >= 0 and index > previous + 1:
            snippet_lines.append("# ...")
        snippet_lines.append(lines[index])
        previous = index
    return "\n".join(snippet_lines).strip()


def _format_code_file(path: Path, snippet: str) -> str:
    language = _language_for_path(path)
    return (
        f"<!-- source: {path.as_posix()} -->\n"
        f"### {path.as_posix()}\n\n"
        f"```{language}\n{snippet}\n```"
    )


def _select_code_files(
    task: str,
    *,
    token_budget: int,
    current_content: str,
    full: bool,
) -> tuple[list[str], list[str], list[str]]:
    included, _, _ = scan_project_files()
    candidates: list[tuple[int, Path, str]] = []
    for rel in included:
        if rel in GENERATED_CONTEXT_FILES or rel.startswith(".octopus/"):
            continue
        path = Path(rel)
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = _code_file_score(path, text, task)
        if score <= 0:
            continue
        candidates.append((score, path, text))

    candidates.sort(key=lambda item: (-item[0], item[1].as_posix()))
    blocks: list[str] = []
    included_files: list[str] = []
    skipped: list[str] = []
    running = current_content
    max_files = 8 if full else 5
    for _, path, _ in candidates[: max_files * 2]:
        snippet = _snippet_for_file(path, task)
        if not snippet:
            continue
        block = _format_code_file(path, snippet)
        if not full and estimate_tokens(f"{running}\n\n{block}") > token_budget:
            skipped.append(f"{path.as_posix()} (budget)")
            continue
        blocks.append(block)
        included_files.append(path.as_posix())
        running = f"{running}\n\n{block}"
        if len(included_files) >= max_files:
            break
    return blocks, included_files, skipped


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

    code_blocks, included_code_files, skipped_code_files = _select_code_files(
        task,
        token_budget=token_budget,
        current_content=current_content,
        full=full,
    )
    if code_blocks:
        body.extend(["## Relevant Code Context", ""])
        body.extend(code_blocks)
        body.append("")
        current_content = f"{current_content}\n\n" + "\n\n".join(code_blocks)
    skipped_sections.extend(skipped_code_files)

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
    token_status = get_token_status(token_count)
    if not full and token_count > token_budget:
        token_status = "over_budget"

    _, excluded_files, excluded_patterns = scan_project_files()
    result = ContextBuildResult(
        task=task,
        profile="full" if full else profile,
        output_path=CURRENT_CONTEXT.as_posix(),
        estimated_tokens=token_count,
        token_status=token_status,
        included_files=[*included_plan_files, *included_code_files],
        included_sections=included_sections,
        skipped_sections=skipped_sections,
        excluded_files=excluded_files,
        excluded_patterns=excluded_patterns,
    )
    if write:
        atomic_write_text(CURRENT_CONTEXT, content)
    return content, result


def build_direction_context(
    state: ProjectState,
    direction_id: str,
    *,
    target: str = "codex",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    write: bool = True,
) -> tuple[str, ContextBuildResult]:
    direction = get_direction(direction_id)
    task = f"{direction.direction_id}: {direction.title}"
    planning_blocks = _direction_planning_blocks()
    current_content = "\n\n".join(planning_blocks)
    code_blocks, included_code_files, skipped_code_files = _select_direction_code_files(
        direction,
        token_budget=token_budget,
        current_content=current_content,
    )
    included_files = [
        path.as_posix()
        for path in (SELECTED_DIRECTION_YAML, NEXT_STEPS_MD, EXPERIMENT_MEMORY_MD, BEST_RUNS_MD)
        if path.exists()
    ]
    included_files.extend(included_code_files)
    body = [
        "# Octopus Current Context",
        "",
        f"> Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"> Target: {target}",
        f"> Direction: {direction.direction_id}",
        "> Estimated tokens: pending",
        "",
        "## 1. Current Task",
        "",
        f"Implement only the selected direction: {direction.title}.",
        "",
        "## 2. Selected Direction",
        "",
        f"- ID: {direction.direction_id}",
        f"- Title: {direction.title}",
        f"- Recommendation: {direction.recommendation}",
        f"- Confidence: {direction.confidence}",
        f"- Risk: {direction.risk}",
        f"- Cost: {direction.cost}",
        f"- Expected impact: {direction.expected_impact or 'not specified'}",
        "",
        direction.rationale,
        "",
        "## 3. Evidence",
        "",
        *_bullet_list(direction.evidence),
        "",
        "## 4. Files to Read",
        "",
        *_path_bullets(direction.files_to_read),
        "",
        "## 5. Likely Files to Edit",
        "",
        *_path_bullets(direction.files_to_edit),
        "",
        "## 6. Files to Avoid",
        "",
        *_path_bullets(
            direction.files_to_avoid
            or [
                "data/",
                "datasets/",
                "checkpoints/",
                "wandb/",
                "mlruns/",
                ".env",
                "secrets.yaml",
            ]
        ),
        "",
        "## 7. Commands to Run",
        "",
        "```bash",
        *(direction.commands_to_run or ["pytest -q"]),
        "```",
        "",
        "## 8. Guardrails",
        "",
        *_bullet_list(direction.guardrails),
        "- Do not read or copy raw data rows, secrets, checkpoints, or large logs into context.",
        "- Do not implement multiple directions at once.",
        "",
        "## 9. Definition of Done",
        "",
        f"- Complete selected direction `{direction.direction_id}` only.",
        "- Add or update tests when applicable.",
        "- Run the listed commands when possible.",
        f"- Stop condition: {direction.stop_condition or 'one controlled experiment is ready.'}",
        "- Ingest the next run with `octopus exp ingest --run-dir <new_run_dir>`.",
        "",
        "## 10. Relevant Planning Context",
        "",
        *planning_blocks,
        "",
        "## 11. Relevant Code Context",
        "",
        *(code_blocks or ["_No matching code files found._"]),
        "",
    ]
    content = "\n".join(body)
    token_count = estimate_tokens(content)
    content = content.replace("> Estimated tokens: pending", f"> Estimated tokens: {token_count}")
    token_status = get_token_status(token_count)
    if token_count > token_budget:
        token_status = "over_budget"

    _, excluded_files, excluded_patterns = scan_project_files()
    result = ContextBuildResult(
        task=task,
        profile=f"direction:{target}",
        output_path=CURRENT_CONTEXT.as_posix(),
        estimated_tokens=token_count,
        token_status=token_status,
        included_files=included_files,
        included_sections=[],
        skipped_sections=skipped_code_files,
        excluded_files=excluded_files,
        excluded_patterns=excluded_patterns,
    )
    if write:
        atomic_write_text(CURRENT_CONTEXT, content)
    return content, result


def _direction_planning_blocks() -> list[str]:
    blocks: list[str] = []
    for path in (SELECTED_DIRECTION_YAML, NEXT_STEPS_MD, EXPERIMENT_MEMORY_MD, BEST_RUNS_MD):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        language = "yaml" if path.suffix in {".yaml", ".yml"} else "markdown"
        blocks.append(
            f"<!-- source: {path.as_posix()} -->\n"
            f"### {path.as_posix()}\n\n"
            f"```{language}\n{text[:6_000]}\n```"
        )
    return blocks or ["_No Phase 2.5 planning files found. Run `octopus exp next` first._"]


def _select_direction_code_files(
    direction: NextDirection,
    *,
    token_budget: int,
    current_content: str,
) -> tuple[list[str], list[str], list[str]]:
    included, _, _ = scan_project_files()
    keywords = _direction_keywords(direction)
    candidates: list[tuple[int, Path, str]] = []
    for rel in included:
        if rel in GENERATED_CONTEXT_FILES or rel.startswith(".octopus/"):
            continue
        path = Path(rel)
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = _direction_file_score(path, text, keywords, direction)
        if score > 0:
            candidates.append((score, path, text))
    candidates.sort(key=lambda item: (-item[0], item[1].as_posix()))

    blocks: list[str] = []
    files: list[str] = []
    skipped: list[str] = []
    running = current_content
    for _, path, _ in candidates[:12]:
        snippet = _snippet_for_file(path, direction.title)
        if not snippet:
            continue
        block = _format_code_file(path, snippet)
        if estimate_tokens(f"{running}\n\n{block}") > token_budget:
            skipped.append(f"{path.as_posix()} (budget)")
            continue
        blocks.append(block)
        files.append(path.as_posix())
        running = f"{running}\n\n{block}"
        if len(files) >= 6:
            break
    return blocks, files, skipped


def _direction_keywords(direction: NextDirection) -> set[str]:
    text = " ".join(
        [
            direction.title,
            direction.rationale,
            " ".join(direction.files_to_read),
            " ".join(direction.files_to_edit),
        ]
    ).lower()
    keywords = set(_task_words(text))
    for group, values in DIRECTION_KEYWORDS.items():
        if group in text or any(value in text for value in values):
            keywords.update(values)
    return {keyword for keyword in keywords if len(keyword) >= 2}


def _direction_file_score(
    path: Path, text: str, keywords: set[str], direction: NextDirection
) -> int:
    rel = path.as_posix().lower()
    haystack = text[:8_000].lower()
    score = 0
    for keyword in keywords:
        if keyword in rel:
            score += 8
        if keyword in haystack:
            score += 3
    for explicit in [*direction.files_to_read, *direction.files_to_edit]:
        normalized = explicit.lower()
        if normalized and normalized in rel:
            score += 10
    return score


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None."]


def _path_bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items] if items else ["- None."]
