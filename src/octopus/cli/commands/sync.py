from rich.console import Console

from octopus.core.files import atomic_write_text, backup_if_exists
from octopus.core.guards import require_complete_state
from octopus.core.paths import AGENTS_MD, CLAUDE_MD
from octopus.planners.rendering import render_template
from octopus.storage.state_store import load_state

console = Console()


def sync_runtime(runtime: str | None = None) -> None:
    require_complete_state()
    state = load_state()
    runtimes = [runtime] if runtime else state.runtime
    updated: list[str] = []
    if "claude" in runtimes:
        backup_if_exists(CLAUDE_MD)
        atomic_write_text(CLAUDE_MD, render_template("CLAUDE.md.j2", state))
        updated.append(CLAUDE_MD.as_posix())
    if "codex" in runtimes:
        backup_if_exists(AGENTS_MD)
        atomic_write_text(AGENTS_MD, render_template("AGENTS.md.j2", state))
        updated.append(AGENTS_MD.as_posix())
    console.print("[green]Synced.[/green]\n")
    for path in updated:
        console.print(f"  {path} updated")
