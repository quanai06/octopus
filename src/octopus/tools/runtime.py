from __future__ import annotations

import re
from pathlib import Path

from octopus.context.builder import build_context, build_direction_context
from octopus.context.profiles import normalize_profile
from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    AGENTS_MD,
    CLAUDE_MD,
    CURRENT_CONTEXT,
    EXPERIMENT_MD,
    ML_DESIGN_MD,
    OCTOPUS_DIR,
    REQUIREMENTS_MD,
    STATE_FILE,
    TASKS_MD,
)
from octopus.core.workflow import requires_baseline_gate
from octopus.experiments.baseline_profile import profile_baseline, write_baseline_profile_md
from octopus.experiments.ingest import ingest_run_dir
from octopus.storage.state_store import load_state
from octopus.storage.task_store import (
    ensure_tasks,
    mark_baseline_tasks_done,
    next_unblocked_task,
    render_tasks_markdown,
)
from octopus.tools.contracts import (
    BuildContextInput,
    BuildContextOutput,
    ContextStatus,
    FileStatus,
    IngestRunInput,
    IngestRunOutput,
    ProfileBaselineInput,
    ProfileBaselineOutput,
    StatusInput,
    StatusOutput,
    TaskNextInput,
    TaskNextOutput,
)


def status_tool(input_data: StatusInput) -> StatusOutput:
    if not OCTOPUS_DIR.exists():
        return StatusOutput(
            initialized=False,
            state_collected=False,
            project_complete=False,
            next_suggested_command="octopus init",
        )
    if not STATE_FILE.exists():
        return StatusOutput(
            initialized=True,
            state_collected=False,
            project_complete=False,
            next_suggested_command="octopus ask",
        )

    state = load_state()
    project_complete = bool(state.project_name)
    next_command = "octopus ask" if not project_complete else "octopus task next"
    files = _file_statuses() if input_data.include_files else []
    context = _context_status() if input_data.include_context else None
    next_task = None
    if input_data.include_tasks and project_complete:
        next_task = next_unblocked_task(ensure_tasks(state))
        if next_task is not None:
            next_command = f"octopus task start {next_task.id}"
    return StatusOutput(
        initialized=True,
        state_collected=True,
        project_complete=project_complete,
        next_suggested_command=next_command,
        project={
            "name": state.project_name,
            "type": state.task_type or state.project_type,
            "input": state.input_type,
            "output": state.output_type,
            "metric": state.main_metric,
            "baseline": state.baseline_model or "default for task type",
            "gpu": state.compute.has_gpu,
            "runtime": state.runtime,
        },
        files=files,
        context=context,
        next_task=next_task,
    )


def task_next_tool(input_data: TaskNextInput) -> TaskNextOutput:
    del input_data
    state = load_state()
    task = next_unblocked_task(ensure_tasks(state))
    if task is None:
        return TaskNextOutput(message="No unblocked todo task found.")
    return TaskNextOutput(
        task=task,
        start_command=f"octopus task start {task.id}",
        message=f"{task.id}: {task.title}",
    )


def build_context_tool(input_data: BuildContextInput) -> BuildContextOutput:
    state = load_state()
    if input_data.direction:
        content, result = build_direction_context(
            state,
            input_data.direction,
            target=input_data.target,
            token_budget=input_data.budget,
            write=input_data.write,
        )
    else:
        profile = normalize_profile(input_data.profile)
        content, result = build_context(
            state,
            input_data.task or "review current project state",
            profile=profile,
            token_budget=input_data.budget,
            full=input_data.full,
            write=input_data.write,
        )
    return BuildContextOutput(
        result=result,
        content=content if input_data.include_content else None,
    )


def ingest_run_tool(input_data: IngestRunInput) -> IngestRunOutput:
    if (
        input_data.run_dir is None
        and input_data.metrics_path is None
        and input_data.report_path is None
    ):
        raise ValueError("Provide run_dir, metrics_path, or report_path.")
    record = ingest_run_dir(
        input_data.run_dir or Path("."),
        metrics_path=input_data.metrics_path,
        report_path=input_data.report_path,
        config_path=input_data.config_path,
        name=input_data.name,
        kind=input_data.kind,
        model=input_data.model,
        dataset=input_data.dataset,
        notes=input_data.notes,
        tags=input_data.tags,
        tracker=input_data.tracker,
    )
    marked = _mark_baseline_tasks_if_needed(record.kind, record.status)
    return IngestRunOutput(
        record=record,
        baseline_tasks_marked_done=marked,
        next_command=f"octopus exp analyze {record.id}",
    )


def profile_baseline_tool(input_data: ProfileBaselineInput) -> ProfileBaselineOutput:
    profile = profile_baseline(input_data.experiment_id, top_k=input_data.top_k)
    output = write_baseline_profile_md(profile) if input_data.write_report else None
    return ProfileBaselineOutput(
        profile=profile,
        output_path=output.as_posix() if output else None,
    )


def _file_statuses() -> list[FileStatus]:
    paths = [REQUIREMENTS_MD, ML_DESIGN_MD, EXPERIMENT_MD, TASKS_MD, CLAUDE_MD, AGENTS_MD]
    return [FileStatus(path=path.as_posix(), exists=path.exists()) for path in paths]


def _context_status() -> ContextStatus:
    status = ContextStatus(path=CURRENT_CONTEXT.as_posix(), exists=CURRENT_CONTEXT.exists())
    if not CURRENT_CONTEXT.exists():
        return status
    text = CURRENT_CONTEXT.read_text(encoding="utf-8")
    token_line = next(
        (line for line in text.splitlines() if line.startswith("> Estimated tokens:")),
        "",
    )
    match = re.search(r"(\d+)", token_line)
    if match:
        status.estimated_tokens = int(match.group(1))
    status.modified_at = CURRENT_CONTEXT.stat().st_mtime
    return status


def _mark_baseline_tasks_if_needed(kind: str, status: str) -> bool:
    if kind != "baseline" or status != "completed" or not STATE_FILE.exists():
        return False
    state = load_state()
    if not requires_baseline_gate(state):
        return False
    tasks = mark_baseline_tasks_done(ensure_tasks(state))
    atomic_write_text(TASKS_MD, render_tasks_markdown(state, tasks))
    return True
