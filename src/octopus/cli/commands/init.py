from rich.console import Console

from octopus.core.config import default_config, save_config
from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    ADR_DIR,
    AGENTS_MD,
    CLAUDE_MD,
    COMPUTE_BUDGET_MD,
    CONFIG_FILE,
    CONTEXT_DIR,
    DATA_STRATEGY_MD,
    EXPERIMENT_MD,
    EXPERIMENTS_DIR,
    ML_DESIGN_MD,
    OCTOPUS_DIR,
    REPORTS_DIR,
    REQUIREMENTS_MD,
    TASKS_MD,
)
from octopus.core.schemas import ProjectState
from octopus.planners.ml_planner import render_ml_plan
from octopus.planners.ml_rules import GENERIC_RULES
from octopus.planners.rendering import render_template
from octopus.storage.state_store import save_state

console = Console()


def parse_runtime(runtime: str | None) -> list[str]:
    if not runtime:
        return []
    values = [item.strip().lower() for item in runtime.split(",") if item.strip()]
    return [] if values == ["none"] else values


def init_project(runtime: str = "claude,codex", force: bool = False) -> None:
    if OCTOPUS_DIR.exists() and not force:
        import questionary

        confirmed = questionary.confirm(
            ".octopus already exists. Overwrite generated files?", default=False
        ).ask()
        if not confirmed:
            console.print("[yellow]Initialization cancelled.[/yellow]")
            return

    runtimes = parse_runtime(runtime)
    for directory in (OCTOPUS_DIR, CONTEXT_DIR, EXPERIMENTS_DIR, REPORTS_DIR, ADR_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    save_config(default_config(runtimes))
    state = ProjectState(runtime=runtimes)
    save_state(state)

    generic = {
        "baseline_models": GENERIC_RULES.baseline_models,
        "metrics": GENERIC_RULES.metrics,
        "risks": GENERIC_RULES.risks,
        "first_experiment_note": GENERIC_RULES.first_experiment_note,
        "main_metric": state.main_metric or GENERIC_RULES.metrics[0],
    }
    atomic_write_text(REQUIREMENTS_MD, render_template("requirements.md.j2", state))
    render_ml_plan(state, backup=False)
    atomic_write_text(TASKS_MD, render_template("tasks.md.j2", state, **generic))
    if "claude" in runtimes:
        atomic_write_text(CLAUDE_MD, render_template("CLAUDE.md.j2", state))
    if "codex" in runtimes:
        atomic_write_text(AGENTS_MD, render_template("AGENTS.md.j2", state))

    created = [
        CONFIG_FILE,
        REQUIREMENTS_MD,
        ML_DESIGN_MD,
        EXPERIMENT_MD,
        DATA_STRATEGY_MD,
        COMPUTE_BUDGET_MD,
        TASKS_MD,
    ]
    if "claude" in runtimes:
        created.append(CLAUDE_MD)
    if "codex" in runtimes:
        created.append(AGENTS_MD)

    console.print("[green]Octopus initialized successfully.[/green]\n")
    console.print("Created:")
    for path in created:
        console.print(f"  {path.as_posix()}")
    console.print("\nNext step:\n  octopus ask")
