import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from octopus.core.paths import STATE_FILE
from octopus.core.schemas import ProjectState


def load_state() -> ProjectState:
    if not STATE_FILE.exists():
        raise FileNotFoundError(STATE_FILE)
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return ProjectState.model_validate(data)


def save_state(state: ProjectState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = state.model_dump(mode="json")
    atomic_write_json(STATE_FILE, data)


def state_exists() -> bool:
    return STATE_FILE.exists()


def merge_state(updates: dict[str, Any]) -> ProjectState:
    state = load_state() if state_exists() else ProjectState()
    data = state.model_dump()
    data.update(updates)
    data["last_updated"] = datetime.now(UTC)
    merged = ProjectState.model_validate(data)
    save_state(merged)
    return merged


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
