from datetime import UTC, datetime
from typing import Any

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import CONFIG_FILE


def default_config(runtime: list[str]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return {
        "version": "0.1.0",
        "runtime": runtime,
        "created_at": now,
        "last_updated": now,
    }


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(CONFIG_FILE)
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}


def save_config(config: dict[str, Any]) -> None:
    atomic_write_text(CONFIG_FILE, yaml.safe_dump(config, sort_keys=False))


def touch_config() -> None:
    config = load_config()
    config["last_updated"] = datetime.now(UTC).isoformat(timespec="seconds")
    save_config(config)
