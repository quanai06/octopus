"""Runtime home layout for embedding Octopus into Claude Code and Codex.

Maps a runtime to its on-disk home and the directories Octopus writes into.
``home`` is the base directory that contains ``.claude`` / ``.codex`` (defaults
to the user's home directory; tests pass a temp dir).
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_RUNTIMES = ("claude", "codex")

# The command that the Claude PreToolUse hook runs.
HOOK_COMMAND = "python -m octopus.install.hooks baseline-guard"

MANIFEST_NAME = ".octopus-manifest.json"


def default_home() -> Path:
    return Path.home()


def runtime_root(runtime: str, home: Path | None = None) -> Path:
    base = home or default_home()
    if runtime == "claude":
        return base / ".claude"
    if runtime == "codex":
        return base / ".codex"
    raise ValueError(f"Unsupported runtime: {runtime}")


def claude_commands_dir(root: Path) -> Path:
    return root / "commands"


def claude_agents_dir(root: Path) -> Path:
    return root / "agents"


def claude_settings_file(root: Path) -> Path:
    return root / "settings.json"


def codex_prompts_dir(root: Path) -> Path:
    return root / "prompts"


def manifest_file(root: Path) -> Path:
    return root / MANIFEST_NAME


def parse_runtimes(value: str) -> list[str]:
    runtimes = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [item for item in runtimes if item not in SUPPORTED_RUNTIMES]
    if invalid:
        raise ValueError(f"Unsupported runtime(s): {', '.join(invalid)}")
    return runtimes
