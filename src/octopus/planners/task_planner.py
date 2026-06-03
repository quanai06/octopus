from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import TASKS_MD
from octopus.core.schemas import ProjectState
from octopus.planners.ml_rules import rules_for_task
from octopus.planners.rendering import render_template


def render_tasks(state: ProjectState, *, backup: bool = True) -> str:
    rules = rules_for_task(state.task_type if state.task_type != "rag" else "rag")
    backup_if_exists(TASKS_MD) if backup else None
    content = render_template("tasks.md.j2", state, baseline_models=rules.baseline_models)
    atomic_write_text(TASKS_MD, content)
    return content
