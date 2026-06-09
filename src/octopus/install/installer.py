"""Install / uninstall Octopus artifacts into AI runtime homes.

Writes thin command routers (and, from Phase 4, agent definitions) into Claude
Code and Codex, plus a PreToolUse baseline-guard hook for Claude. Every install
records a manifest so uninstall removes exactly what it created and nothing else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from octopus.core.files import atomic_write_text
from octopus.install.artifacts import (
    AGENT_DEFS,
    CODEX_SKILLS,
    COMMAND_ROUTERS,
    render_agent_def,
    render_codex_prompt,
    render_codex_skill,
    render_codex_skill_openai_yaml,
    render_command_router,
)
from octopus.install.layout import (
    HOOK_COMMAND,
    claude_agents_dir,
    claude_commands_dir,
    claude_settings_file,
    codex_prompts_dir,
    codex_skills_dir,
    manifest_file,
    runtime_root,
)


@dataclass
class InstallResult:
    runtime: str
    root: Path
    files: list[Path] = field(default_factory=list)
    hook_added: bool = False


def install(
    runtimes: list[str], home: Path | None = None, force: bool = False
) -> list[InstallResult]:
    results: list[InstallResult] = []
    for runtime in runtimes:
        root = runtime_root(runtime, home)
        if runtime == "claude":
            results.append(_install_claude(root, force))
        elif runtime == "codex":
            results.append(_install_codex(root, force))
    return results


def uninstall(runtimes: list[str], home: Path | None = None) -> list[InstallResult]:
    results: list[InstallResult] = []
    for runtime in runtimes:
        root = runtime_root(runtime, home)
        result = InstallResult(runtime=runtime, root=root)
        manifest = _read_manifest(root)
        for rel in manifest.get("files", []):
            path = root / rel
            if path.exists():
                path.unlink()
                result.files.append(path)
        if manifest.get("hook_added") and runtime == "claude":
            result.hook_added = _remove_hook(claude_settings_file(root))
        manifest_path = manifest_file(root)
        if manifest_path.exists():
            manifest_path.unlink()
        results.append(result)
    return results


# --- per-runtime install ---------------------------------------------------


def _install_claude(root: Path, force: bool) -> InstallResult:
    result = InstallResult(runtime="claude", root=root)
    commands_dir = claude_commands_dir(root)
    commands_dir.mkdir(parents=True, exist_ok=True)
    for router in COMMAND_ROUTERS:
        path = commands_dir / f"{router.name}.md"
        _write(path, render_command_router(router), force)
        result.files.append(path)

    if AGENT_DEFS:
        agents_dir = claude_agents_dir(root)
        agents_dir.mkdir(parents=True, exist_ok=True)
        for agent in AGENT_DEFS:
            path = agents_dir / f"{agent.name}.md"
            _write(path, render_agent_def(agent), force)
            result.files.append(path)

    result.hook_added = _add_hook(claude_settings_file(root))
    _write_manifest(root, result)
    return result


def _install_codex(root: Path, force: bool) -> InstallResult:
    result = InstallResult(runtime="codex", root=root)
    prompts_dir = codex_prompts_dir(root)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for router in COMMAND_ROUTERS:
        path = prompts_dir / f"{router.name}.md"
        _write(path, render_codex_prompt(router), force)
        result.files.append(path)

    if CODEX_SKILLS:
        skills_dir = codex_skills_dir(root)
        skills_dir.mkdir(parents=True, exist_ok=True)
        for skill in CODEX_SKILLS:
            skill_dir = skills_dir / skill.name
            agents_dir = skill_dir / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            skill_path = skill_dir / "SKILL.md"
            _write(skill_path, render_codex_skill(skill), force)
            result.files.append(skill_path)
            metadata_path = agents_dir / "openai.yaml"
            _write(metadata_path, render_codex_skill_openai_yaml(skill), force)
            result.files.append(metadata_path)

    _write_manifest(root, result)
    return result


# --- settings.json hook merge ---------------------------------------------


def _add_hook(settings_path: Path) -> bool:
    settings = _read_json(settings_path)
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if _hook_present(pre_tool_use):
        return False
    pre_tool_use.append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": HOOK_COMMAND}]}
    )
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(settings_path, json.dumps(settings, indent=2) + "\n")
    return True


def _remove_hook(settings_path: Path) -> bool:
    if not settings_path.exists():
        return False
    settings = _read_json(settings_path)
    hooks = settings.get("hooks", {})
    pre_tool_use = hooks.get("PreToolUse", [])
    new_entries = []
    removed = False
    for entry in pre_tool_use:
        inner = [h for h in entry.get("hooks", []) if h.get("command") != HOOK_COMMAND]
        if len(inner) != len(entry.get("hooks", [])):
            removed = True
        if inner:
            entry = {**entry, "hooks": inner}
            new_entries.append(entry)
        elif not entry.get("hooks"):
            new_entries.append(entry)
    if removed:
        if new_entries:
            hooks["PreToolUse"] = new_entries
        else:
            hooks.pop("PreToolUse", None)
        if not hooks:
            settings.pop("hooks", None)
        atomic_write_text(settings_path, json.dumps(settings, indent=2) + "\n")
    return removed


def _hook_present(pre_tool_use: list) -> bool:
    for entry in pre_tool_use:
        for hook in entry.get("hooks", []):
            if hook.get("command") == HOOK_COMMAND:
                return True
    return False


# --- manifest --------------------------------------------------------------


def _write_manifest(root: Path, result: InstallResult) -> None:
    payload = {
        "runtime": result.runtime,
        "files": [path.relative_to(root).as_posix() for path in result.files],
        "hook_added": result.hook_added,
    }
    atomic_write_text(manifest_file(root), json.dumps(payload, indent=2) + "\n")


def _read_manifest(root: Path) -> dict:
    return _read_json(manifest_file(root))


# --- helpers ---------------------------------------------------------------


def _write(path: Path, content: str, force: bool) -> None:
    # Routers/agents are managed artifacts: refresh them in place on every
    # (re)install. ``force`` is reserved for future opt-in overwrite prompts.
    atomic_write_text(path, content)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
