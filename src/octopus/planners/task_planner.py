from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import TASKS_MD
from octopus.core.schemas import ProjectState
from octopus.storage.task_store import ensure_tasks, render_tasks_markdown


def render_tasks(state: ProjectState, *, backup: bool = True) -> str:
    backup_if_exists(TASKS_MD) if backup else None
    tasks = ensure_tasks(state)
    content = render_tasks_markdown(state, tasks)
    atomic_write_text(TASKS_MD, content)
    return content
