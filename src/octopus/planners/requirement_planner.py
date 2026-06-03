from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.paths import REQUIREMENTS_MD
from octopus.core.schemas import ProjectState
from octopus.planners.rendering import render_template


def render_requirements(state: ProjectState, *, backup: bool = True) -> str:
    backup_if_exists(REQUIREMENTS_MD) if backup else None
    content = render_template("requirements.md.j2", state)
    atomic_write_text(REQUIREMENTS_MD, content)
    return content
