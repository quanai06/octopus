"""Short-term, in-session memory.

A single active session captures what is happening *right now* — current task,
selected direction, last ingested run, and a small event log — so a Claude/Codex
session can be restored after a context reset via ``octopus resume``.

This is distinct from `.octopus/memory/` (long-term experiment memory). The
session is RAM; memory is the archive. YAML/JSON is the source of truth; the
markdown view is regenerated on every change.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from octopus.core.files import atomic_write_text
from octopus.core.paths import SESSION_DIR, SESSION_MD, SESSION_STATE
from octopus.core.schemas import SessionEvent, SessionState

_MAX_EVENTS = 50


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def session_active() -> bool:
    state = load_session()
    return state is not None and state.status == "active"


def load_session() -> SessionState | None:
    if not SESSION_STATE.exists():
        return None
    try:
        data = json.loads(SESSION_STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return SessionState.model_validate(data)


def save_session(state: SessionState) -> None:
    state.updated_at = _now()
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(SESSION_STATE, state.model_dump_json(indent=2))
    atomic_write_text(SESSION_MD, render_session_md(state))


def start_session(goal: str | None = None) -> SessionState:
    timestamp = datetime.now(UTC)
    state = SessionState(
        session_id="S" + timestamp.strftime("%Y%m%d%H%M%S"),
        started_at=_now(),
        updated_at=_now(),
        status="active",
        goal=goal,
    )
    save_session(state)
    return state


def end_session() -> SessionState | None:
    state = load_session()
    if state is None:
        return None
    state.status = "ended"
    save_session(state)
    # Archive the ended session next to the live file.
    archive = SESSION_DIR / f"{state.session_id}.json"
    atomic_write_text(archive, state.model_dump_json(indent=2))
    return state


def log_event(
    kind: str,
    message: str,
    *,
    current_task: str | None = None,
    selected_direction: str | None = None,
    last_run: str | None = None,
) -> SessionState | None:
    state = load_session()
    if state is None or state.status != "active":
        return None
    if current_task is not None:
        state.current_task = current_task
    if selected_direction is not None:
        state.selected_direction = selected_direction
    if last_run is not None:
        state.last_run = last_run
    state.events.append(SessionEvent(timestamp=_now(), kind=kind, message=message))  # type: ignore[arg-type]
    state.events = state.events[-_MAX_EVENTS:]
    save_session(state)
    return state


def record_if_active(
    kind: str,
    message: str,
    *,
    current_task: str | None = None,
    selected_direction: str | None = None,
    last_run: str | None = None,
) -> None:
    """Best-effort capture: no-op unless a session is active."""
    if not session_active():
        return
    log_event(
        kind,
        message,
        current_task=current_task,
        selected_direction=selected_direction,
        last_run=last_run,
    )


def render_session_md(state: SessionState) -> str:
    lines = [
        f"# Session {state.session_id}",
        "",
        f"- Status: {state.status}",
        f"- Started: {state.started_at}",
        f"- Updated: {state.updated_at}",
        f"- Goal: {state.goal or 'not set'}",
        f"- Current task: {state.current_task or 'none'}",
        f"- Selected direction: {state.selected_direction or 'none'}",
        f"- Last run: {state.last_run or 'none'}",
        "",
        "## Recent Events",
        "",
    ]
    if not state.events:
        lines.append("_No events recorded yet._")
    for event in reversed(state.events[-15:]):
        lines.append(f"- `{event.timestamp}` [{event.kind}] {event.message}")
    lines.append("")
    return "\n".join(lines)
