from pathlib import Path

from rich.console import Console

from octopus.install.installer import install, uninstall
from octopus.install.layout import parse_runtimes

console = Console()


def install_runtimes(runtime: str, home: Path | None, force: bool) -> None:
    try:
        runtimes = parse_runtimes(runtime)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("Supported runtimes: claude, codex")
        raise SystemExit(1) from exc
    if not runtimes:
        console.print("[yellow]No runtime selected. Use --runtime claude,codex.[/yellow]")
        return

    results = install(runtimes, home=home, force=force)
    console.print("[green]Octopus installed into runtime(s).[/green]\n")
    for result in results:
        console.print(f"[bold]{result.runtime}[/bold] -> {result.root.as_posix()}")
        for path in result.files:
            console.print(f"  {path.relative_to(result.root).as_posix()}")
        if result.runtime == "claude":
            console.print(
                "  hook: baseline-guard "
                + ("added to settings.json" if result.hook_added else "already present")
            )
    console.print("\nReload your runtime, then try [bold]/octopus-status[/bold].")


def uninstall_runtimes(runtime: str, home: Path | None) -> None:
    try:
        runtimes = parse_runtimes(runtime)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    results = uninstall(runtimes, home=home)
    console.print("[green]Octopus uninstalled.[/green]\n")
    for result in results:
        console.print(
            f"[bold]{result.runtime}[/bold]: removed {len(result.files)} file(s)"
            + (", removed baseline-guard hook" if result.hook_added else "")
        )
