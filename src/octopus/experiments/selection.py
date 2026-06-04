from datetime import UTC, datetime

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import DECISIONS_MD, NEXT_STEPS_YAML, SELECTED_DIRECTION_YAML
from octopus.core.schemas import NextDirection, SelectedDirection


def load_next_directions() -> list[NextDirection]:
    if not NEXT_STEPS_YAML.exists():
        raise FileNotFoundError(NEXT_STEPS_YAML)
    data = yaml.safe_load(NEXT_STEPS_YAML.read_text(encoding="utf-8")) or {}
    return [
        NextDirection.model_validate(item)
        for item in data.get("directions", [])
        if isinstance(item, dict)
    ]


def get_direction(direction_id: str) -> NextDirection:
    for direction in load_next_directions():
        if direction.direction_id == direction_id:
            return direction
    raise KeyError(direction_id)


def choose_direction(direction_id: str) -> SelectedDirection:
    direction = get_direction(direction_id)
    selected = SelectedDirection(
        selected_direction_id=direction.direction_id,
        selected_at=datetime.now(UTC).isoformat(timespec="seconds"),
        source_plan=NEXT_STEPS_YAML.as_posix(),
        status="selected",
    )
    atomic_write_text(
        SELECTED_DIRECTION_YAML,
        yaml.safe_dump(selected.model_dump(mode="json"), sort_keys=False),
    )
    _append_decision(direction, selected)
    return selected


def load_selected_direction() -> SelectedDirection | None:
    if not SELECTED_DIRECTION_YAML.exists():
        return None
    data = yaml.safe_load(SELECTED_DIRECTION_YAML.read_text(encoding="utf-8")) or {}
    return SelectedDirection.model_validate(data)


def _append_decision(direction: NextDirection, selected: SelectedDirection) -> None:
    existing = (
        DECISIONS_MD.read_text(encoding="utf-8")
        if DECISIONS_MD.exists()
        else "# Decision Memory\n"
    ).rstrip()
    block = [
        "",
        f"## {selected.selected_direction_id} selected at {selected.selected_at}",
        f"- Decision: {direction.title}",
        f"- Reason: {direction.rationale}",
        f"- Source: {selected.source_plan}",
        "",
    ]
    atomic_write_text(DECISIONS_MD, f"{existing}\n" + "\n".join(block))
