import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

from octopus.core.files import atomic_write_text
from octopus.core.paths import TASK_STATE_FILE
from octopus.core.schemas import ProjectState, TaskItem
from octopus.planners.ml_planner import selected_baseline_models
from octopus.planners.ml_rules import rules_for_task

BASELINE_TASK_IDS = {"T010", "T011", "T012"}
TaskStatus = Literal["todo", "in_progress", "done"]


def task_state_exists() -> bool:
    return TASK_STATE_FILE.exists()


def default_tasks_for_state(state: ProjectState) -> list[TaskItem]:
    rules = rules_for_task(state.task_type if state.task_type != "rag" else "rag")
    baseline = selected_baseline_models(state, rules)[0]
    split_title = (
        "Verify and persist provided train / val / test split"
        if state.fixed_split_available
        else "Create train / val / test split"
    )
    split_description = (
        "Use the provided fixed split files; do not reshuffle or recreate them."
        if state.fixed_split_available
        else "Create a reproducible split manifest before baseline training."
    )
    tasks = [
        TaskItem(
            id="T001",
            title="Initialize repo and environment",
            priority="high",
            milestone="Milestone 1: Project Setup",
        ),
        TaskItem(
            id="T002",
            title="Define config and project structure",
            priority="high",
            depends_on=["T001"],
            milestone="Milestone 1: Project Setup",
        ),
        TaskItem(
            id="T003",
            title="Load and inspect dataset",
            priority="high",
            depends_on=["T001"],
            milestone="Milestone 2: Data Pipeline",
        ),
        TaskItem(
            id="T004",
            title="Validate schema and check for issues",
            priority="high",
            depends_on=["T003"],
            milestone="Milestone 2: Data Pipeline",
        ),
        TaskItem(
            id="T005",
            title=split_title,
            priority="high",
            depends_on=["T004"],
            milestone="Milestone 2: Data Pipeline",
            description=split_description,
        ),
    ]
    if state.has_class_imbalance:
        tasks.append(
            TaskItem(
                id="T006",
                title="Handle class imbalance (oversampling / class weights)",
                priority="high",
                depends_on=["T005"],
                milestone="Milestone 2: Data Pipeline",
            )
        )
    tasks.extend(
        [
            TaskItem(
                id="T010",
                title=f"Implement baseline model ({baseline})",
                priority="high",
                depends_on=["T005"],
                milestone="Milestone 3: Baseline",
                description="Baseline must be completed before main model work starts.",
            ),
            TaskItem(
                id="T011",
                title="Evaluate baseline on val set",
                priority="high",
                depends_on=["T010"],
                milestone="Milestone 3: Baseline",
            ),
            TaskItem(
                id="T012",
                title="Log baseline results to `.octopus/experiments/`",
                priority="high",
                depends_on=["T011"],
                milestone="Milestone 3: Baseline",
            ),
            TaskItem(
                id="T020",
                title="Implement main model training",
                priority="medium",
                depends_on=["T012"],
                milestone="Milestone 4: Main Model",
                description="Blocked until baseline result is logged.",
            ),
            TaskItem(
                id="T021",
                title="Run first experiment and compare with baseline",
                priority="medium",
                depends_on=["T020"],
                milestone="Milestone 4: Main Model",
            ),
            TaskItem(
                id="T022",
                title="Update experiment_plan.md with results",
                priority="medium",
                depends_on=["T021"],
                milestone="Milestone 4: Main Model",
            ),
            TaskItem(
                id="T030",
                title="Error analysis on val set",
                priority="medium",
                depends_on=["T021"],
                milestone="Milestone 5: Review",
            ),
            TaskItem(
                id="T031",
                title="Suggest next experiment",
                priority="low",
                depends_on=["T030"],
                milestone="Milestone 5: Review",
            ),
            TaskItem(
                id="T032",
                title="Update tasks.md with current status",
                priority="low",
                milestone="Milestone 5: Review",
            ),
        ]
    )
    return tasks


def load_tasks() -> list[TaskItem]:
    if not TASK_STATE_FILE.exists():
        return []
    data = json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
    return [TaskItem.model_validate(item) for item in data.get("tasks", [])]


def save_tasks(tasks: list[TaskItem]) -> Path:
    payload = {"version": "0.1.0", "tasks": [task.model_dump(mode="json") for task in tasks]}
    TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(TASK_STATE_FILE, json.dumps(payload, indent=2) + "\n")
    return TASK_STATE_FILE


def ensure_tasks(state: ProjectState) -> list[TaskItem]:
    defaults = default_tasks_for_state(state)
    existing = {task.id: task for task in load_tasks()}
    merged: list[TaskItem] = []
    for task in defaults:
        previous = existing.pop(task.id, None)
        if previous:
            task.status = previous.status
        merged.append(task)
    merged.extend(existing.values())
    save_tasks(merged)
    return merged


def get_task(tasks: list[TaskItem], task_id: str) -> TaskItem | None:
    normalized = task_id.upper()
    return next((task for task in tasks if task.id.upper() == normalized), None)


def blocked_dependencies(task: TaskItem, tasks: list[TaskItem]) -> list[str]:
    by_id = {item.id: item for item in tasks}
    blocked: list[str] = []
    for dependency in task.depends_on:
        if by_id.get(dependency) is None or by_id[dependency].status != "done":
            blocked.append(dependency)
    return blocked


def next_unblocked_task(tasks: list[TaskItem]) -> TaskItem | None:
    for task in tasks:
        if task.status == "todo" and not blocked_dependencies(task, tasks):
            return task
    return None


def set_task_status(tasks: list[TaskItem], task_id: str, status: TaskStatus) -> TaskItem:
    task = get_task(tasks, task_id)
    if task is None:
        raise KeyError(task_id)
    task.status = status
    save_tasks(tasks)
    return task


def mark_baseline_tasks_done(tasks: list[TaskItem]) -> list[TaskItem]:
    for task in tasks:
        if task.id in BASELINE_TASK_IDS:
            task.status = "done"
    save_tasks(tasks)
    return tasks


def render_tasks_markdown(state: ProjectState, tasks: list[TaskItem]) -> str:
    lines = [
        f"# Tasks - {state.project_name or 'Unnamed Project'}",
        "",
        "> Managed by Octopus CLI. Use `octopus task list`, `octopus task start <id>`,",
        "> and `octopus task done <id>` to update task state.",
        "",
        "---",
        "",
    ]
    groups: dict[str, list[TaskItem]] = defaultdict(list)
    for task in tasks:
        groups[task.milestone or "Unassigned"].append(task)
    for milestone, items in groups.items():
        lines.extend([f"## {milestone}", ""])
        for task in items:
            checkbox = "[x]" if task.status == "done" else "[ ]"
            lines.append(f"- {checkbox} {task.id}: {task.title}")
            depends = ", ".join(task.depends_on) if task.depends_on else "-"
            lines.append(
                f"  - Priority: {task.priority.title()} | Status: {task.status} | "
                f"Depends on: {depends}"
            )
            if task.description:
                lines.append(f"  - Note: {task.description}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
