"""Claude Code PreToolUse hook handlers for Octopus.

Invoked by the host runtime as::

    python -m octopus.install.hooks baseline-guard

The hook reads the tool-call JSON from stdin and exits ``2`` to *block* the
call (Claude Code's block mechanism), or ``0`` to allow it.

``baseline-guard`` blocks shell commands that look like main-model training when
the project requires a baseline and no completed baseline exists yet — the same
rule the CLI enforces, now enforced inside the runtime.
"""

from __future__ import annotations

import json
import re
import sys

# Commands that look like launching a training run.
_TRAIN_PATTERNS = (
    r"train\.py",
    r"\btrainer\b",
    r"\.fit\(",
    r"accelerate\s+launch",
    r"torchrun",
    r"python\s+-m\s+\S*train",
    r"\bfine[-_]?tune\b",
)


def _looks_like_training(command: str) -> bool:
    lowered = command.lower()
    return any(re.search(pattern, lowered) for pattern in _TRAIN_PATTERNS)


def baseline_guard(stdin_text: str) -> int:
    try:
        payload = json.loads(stdin_text or "{}")
    except json.JSONDecodeError:
        return 0
    command = ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = str(tool_input.get("command") or "")
    if not command or not _looks_like_training(command):
        return 0

    # Import lazily so the hook is cheap when it does not apply.
    from octopus.core.workflow import has_completed_baseline, requires_baseline_gate
    from octopus.storage.state_store import load_state, state_exists

    if not state_exists():
        return 0
    try:
        gated = requires_baseline_gate(load_state())
    except Exception:
        return 0
    if gated and not has_completed_baseline():
        print(
            "Octopus baseline-guard: a completed baseline is required before main-model "
            "training. Establish a baseline and run "
            "`octopus exp log --kind baseline ...` (or `octopus exp ingest`) first.",
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv: list[str]) -> int:
    hook = argv[1] if len(argv) > 1 else ""
    if hook in {"baseline-guard", "baseline_guard"}:
        return baseline_guard(sys.stdin.read())
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main(sys.argv))
