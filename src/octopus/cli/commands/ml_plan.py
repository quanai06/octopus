from rich.console import Console

from octopus.core.guards import require_ml_project, require_state
from octopus.planners.ml_planner import render_ml_plan, selected_baseline_models
from octopus.storage.state_store import load_state

console = Console()


def generate_ml_plan(force: bool = False) -> None:
    require_state()
    require_ml_project()
    state = load_state()
    rules = render_ml_plan(state, backup=not force)
    baseline = selected_baseline_models(state, rules)[0]
    if rules.generic:
        console.print("[yellow]Task type not recognized. Generic template used.[/yellow]")
    console.print("[green]ml_design.md generated.[/green]")
    console.print("[green]experiment_plan.md generated.[/green]\n")
    console.print("[green]data_strategy.md generated.[/green]")
    console.print("[green]compute_budget.md generated.[/green]\n")
    console.print(f"  Task:     {state.task_type or 'generic'}")
    console.print(f"  Baseline: {baseline}")
    console.print(f"  Metric:   {state.main_metric or rules.metrics[0]}")
    console.print(f"  Risks:    {len(rules.risks)} identified")
    console.print('\nRun next:\n  octopus tasks\n  octopus context --task "train baseline"')
