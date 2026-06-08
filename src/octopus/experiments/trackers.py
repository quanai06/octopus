"""Read experiment metrics from common ML trackers.

Auto-detects and parses an MLflow / Weights & Biases / TensorBoard run directory
into a normalized ``TrackerRun`` (final scalar metrics + params), so
``octopus exp ingest --run-dir <tracker_run>`` works without hand-written
``metrics.json``.

MLflow and W&B are parsed from their on-disk files with no extra dependency.
TensorBoard needs the optional ``tensorboard`` package; when it is missing,
loading raises ``TrackerImportError`` with an actionable message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

TRACKER_MLFLOW = "mlflow"
TRACKER_WANDB = "wandb"
TRACKER_TENSORBOARD = "tensorboard"

# Summary keys that W&B / TensorBoard add for bookkeeping, not real metrics.
_INTERNAL_KEYS = {"_runtime", "_timestamp", "_step", "_wandb", "global_step"}


class TrackerImportError(RuntimeError):
    """Raised when an optional tracker dependency is required but not installed."""


@dataclass
class TrackerRun:
    source: str
    metrics: dict[str, float] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    name: str | None = None


def detect_tracker(run_dir: Path) -> str | None:
    """Return the tracker kind for ``run_dir``, or None if it is not a tracker run."""
    if (run_dir / "meta.yaml").exists() and (run_dir / "metrics").is_dir():
        return TRACKER_MLFLOW
    if _find_wandb_summary(run_dir) is not None:
        return TRACKER_WANDB
    if _find_event_file(run_dir) is not None:
        return TRACKER_TENSORBOARD
    return None


def load_tracker_run(run_dir: Path, tracker: str = "auto") -> TrackerRun | None:
    """Load a tracker run. ``tracker`` may be auto/mlflow/wandb/tensorboard/none."""
    if tracker == "none":
        return None
    kind = detect_tracker(run_dir) if tracker == "auto" else tracker
    if kind is None:
        return None
    if kind == TRACKER_MLFLOW:
        return _read_mlflow(run_dir)
    if kind == TRACKER_WANDB:
        return _read_wandb(run_dir)
    if kind == TRACKER_TENSORBOARD:
        return _read_tensorboard(run_dir)
    raise ValueError(f"Unknown tracker: {tracker}")


# --- MLflow ----------------------------------------------------------------


def _read_mlflow(run_dir: Path) -> TrackerRun:
    metrics: dict[str, float] = {}
    metrics_dir = run_dir / "metrics"
    if metrics_dir.is_dir():
        for metric_file in sorted(metrics_dir.iterdir()):
            if metric_file.is_file():
                value = _last_mlflow_metric(metric_file)
                if value is not None:
                    metrics[metric_file.name] = value
    params: dict[str, str] = {}
    params_dir = run_dir / "params"
    if params_dir.is_dir():
        for param_file in sorted(params_dir.iterdir()):
            if param_file.is_file():
                params[param_file.name] = param_file.read_text(encoding="utf-8").strip()
    name = None
    meta = run_dir / "meta.yaml"
    if meta.exists():
        data = _read_yaml(meta)
        run_name = data.get("run_name") or (data.get("tags") or {}).get("mlflow.runName")
        if isinstance(run_name, str) and run_name:
            name = run_name
    return TrackerRun(source=TRACKER_MLFLOW, metrics=metrics, params=params, name=name)


def _last_mlflow_metric(path: Path) -> float | None:
    # MLflow metric files are append-only lines of: "<timestamp> <value> <step>".
    last: float | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                last = float(parts[1])
            except ValueError:
                continue
    return last


# --- Weights & Biases ------------------------------------------------------


def _read_wandb(run_dir: Path) -> TrackerRun:
    summary_path = _find_wandb_summary(run_dir)
    metrics: dict[str, float] = {}
    if summary_path is not None:
        summary = _read_json(summary_path)
        metrics = _flatten_numeric(summary)
    params: dict[str, str] = {}
    config_path = _find_wandb_config(run_dir)
    if config_path is not None:
        params = _wandb_config_params(_read_yaml(config_path))
    name = None
    metadata_path = _find_first_recursive(run_dir, "wandb-metadata.json")
    if metadata_path is not None:
        metadata = _read_json(metadata_path)
        candidate = metadata.get("name") or metadata.get("program")
        if isinstance(candidate, str):
            name = candidate
    return TrackerRun(source=TRACKER_WANDB, metrics=metrics, params=params, name=name)


def _wandb_config_params(config: dict[str, Any]) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, value in config.items():
        if key.startswith("_"):
            continue
        # W&B config entries are usually {"value": ...}; fall back to the raw value.
        raw = value.get("value") if isinstance(value, dict) and "value" in value else value
        if isinstance(raw, str | int | float | bool):
            params[key] = str(raw)
    return params


# --- TensorBoard -----------------------------------------------------------


def _read_tensorboard(run_dir: Path) -> TrackerRun:
    try:
        from tensorboard.backend.event_processing.event_accumulator import (  # type: ignore
            EventAccumulator,
        )
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise TrackerImportError(
            "Reading TensorBoard event files needs the 'tensorboard' package. "
            "Install it with: pip install tensorboard"
        ) from exc

    event_file = _find_event_file(run_dir)
    target = str(event_file.parent if event_file else run_dir)
    accumulator = EventAccumulator(target)
    accumulator.Reload()
    metrics: dict[str, float] = {}
    for tag in accumulator.Tags().get("scalars", []):
        events = accumulator.Scalars(tag)
        if events:
            metrics[tag] = float(events[-1].value)
    return TrackerRun(source=TRACKER_TENSORBOARD, metrics=metrics, name=run_dir.name)


# --- helpers ---------------------------------------------------------------


def _flatten_numeric(data: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in data.items():
        if key in _INTERNAL_KEYS or key.startswith("_"):
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            metrics[key] = float(value)
    return metrics


def _find_wandb_summary(run_dir: Path) -> Path | None:
    return _find_first_recursive(run_dir, "wandb-summary.json")


def _find_wandb_config(run_dir: Path) -> Path | None:
    direct = _find_first_recursive(run_dir, "config.yaml")
    return direct


def _find_event_file(run_dir: Path) -> Path | None:
    if not run_dir.exists():
        return None
    matches = sorted(run_dir.rglob("events.out.tfevents.*"))
    return matches[0] if matches else None


def _find_first_recursive(run_dir: Path, filename: str, max_depth: int = 3) -> Path | None:
    if not run_dir.exists():
        return None
    direct = run_dir / filename
    if direct.exists():
        return direct
    matches = sorted(run_dir.rglob(filename))
    for match in matches:
        if len(match.relative_to(run_dir).parts) <= max_depth:
            return match
    return None


def _read_json(path: Path) -> dict[str, Any]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}
