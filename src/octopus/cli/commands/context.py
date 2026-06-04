from rich.console import Console

from octopus.context.builder import build_context, build_direction_context
from octopus.context.profiles import normalize_profile
from octopus.context.token_estimator import format_token_display
from octopus.core.guards import require_plan_files, require_state
from octopus.storage.state_store import load_state

console = Console()


def build_current_context(
    task: str | None,
    inspect_arg: str | None = None,
    *,
    profile: str = "training",
    budget: int = 6000,
    full: bool = False,
    direction: str | None = None,
    target: str = "codex",
) -> None:
    require_state()
    inspect = inspect_arg == "inspect"
    if inspect_arg and not inspect:
        console.print("[red]Unknown context action.[/red]")
        console.print("Use: octopus context inspect")
        raise SystemExit(1)
    if direction:
        if budget <= 0:
            console.print("[red]Budget must be greater than zero.[/red]")
            raise SystemExit(1)
        try:
            content, result = build_direction_context(
                load_state(),
                direction,
                target=target,
                token_budget=budget,
                write=not inspect,
            )
        except (FileNotFoundError, KeyError) as exc:
            console.print(f"[red]Direction context unavailable: {exc}[/red]")
            console.print("Run: octopus exp next")
            raise SystemExit(1) from exc
        if inspect:
            console.print(content)
            return
        _print_context_result(result)
        return

    require_plan_files()
    try:
        context_profile = normalize_profile(profile)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if budget <= 0:
        console.print("[red]Budget must be greater than zero.[/red]")
        raise SystemExit(1)

    task_name = task or "review current project state"
    content, result = build_context(
        load_state(),
        task_name,
        profile=context_profile,
        token_budget=budget,
        full=full,
        write=not inspect,
    )
    if inspect:
        console.print(content)
        return

    _print_context_result(result)


def _print_context_result(result) -> None:
    console.print("[green]Context built.[/green]\n")
    console.print(f"  Task:    {result.task}")
    console.print(f"  Profile: {result.profile}")
    console.print(f"  Output:  {result.output_path}")
    console.print(f"  Tokens:  {format_token_display(result.estimated_tokens)}")
    console.print("\n  Included:")
    for path in result.included_files:
        console.print(f"    {path}")
    if result.included_sections:
        console.print("\n  Sections:")
        for section in result.included_sections:
            console.print(f"    {section}")
    if result.skipped_sections:
        console.print("\n  Skipped:")
        for section in result.skipped_sections:
            console.print(f"    {section}")
    if result.token_status == "warning":
        console.print(
            "\n[yellow]Token warning: consider splitting the task into smaller steps.[/yellow]"
        )
    elif result.token_status == "over_budget":
        console.print(
            "\n[yellow]Token budget exceeded: some sections/files were skipped, but fixed "
            "task overhead is still above the requested budget.[/yellow]"
        )
    elif result.token_status == "exceeded":
        console.print(
            "\n[red]Token limit exceeded: split the task before handing it to an agent.[/red]"
        )
