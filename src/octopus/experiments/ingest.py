import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from octopus.core.guards import require_init
from octopus.core.schemas import ExperimentArtifacts, ExperimentRecord, PerClassMetrics
from octopus.experiments.trackers import TrackerRun, load_tracker_run
from octopus.storage.experiment_store import next_experiment_id, save_experiment


def read_metrics_json(path: Path) -> dict[str, float]:
    data = _read_json(path)
    metrics: dict[str, float] = {}
    for key, value in data.items():
        if isinstance(value, int | float) and not isinstance(value, bool):
            metrics[_normalize_metric_key(key)] = float(value)
    return metrics


def read_classification_report(path: Path) -> dict[str, Any]:
    return _read_json(path)


def read_trainer_state(path: Path) -> dict[str, Any]:
    return _read_json(path)


def infer_experiment_metadata(run_dir: Path) -> dict[str, Any]:
    name = _slug(run_dir.name) or "training_run"
    kind = "baseline" if "baseline" in name else "main"
    metadata: dict[str, Any] = {"name": name, "kind": kind}
    config = _find_first(run_dir, ("config.yaml", "config.yml"))
    if config:
        config_data = _read_yaml(config)
        metadata["model"] = _first_present(config_data, ("model", "model_name", "backbone"))
        metadata["dataset"] = _first_present(config_data, ("dataset", "dataset_name", "data"))
        metadata["config_path"] = config.as_posix()
    return metadata


def ingest_run_dir(
    run_dir: Path,
    *,
    metrics_path: Path | None = None,
    report_path: Path | None = None,
    config_path: Path | None = None,
    name: str | None = None,
    kind: str | None = None,
    model: str | None = None,
    dataset: str | None = None,
    status: str = "completed",
    notes: list[str] | None = None,
    tags: list[str] | None = None,
    tracker: str = "auto",
) -> ExperimentRecord:
    require_init()
    run_dir = run_dir.expanduser()
    if not run_dir.exists() and not (metrics_path or report_path):
        raise FileNotFoundError(run_dir)

    metrics_file = metrics_path or _find_first(run_dir, ("metrics.json",))
    report_file = report_path or _find_first(run_dir, ("classification_report.json", "report.json"))
    trainer_state_file = _find_first(run_dir, ("trainer_state.json",))
    config_file = config_path or _find_first(run_dir, ("config.yaml", "config.yml"))
    log_file = _find_first(run_dir, ("train.log", "training.log"))

    metadata = infer_experiment_metadata(run_dir) if run_dir.exists() else {}
    metrics: dict[str, float] = {}
    per_class: dict[str, PerClassMetrics] = {}

    tracker_run = load_tracker_run(run_dir, tracker) if run_dir.exists() else None
    if tracker_run is not None:
        _merge_tracker(metrics, metadata, tracker_run)

    if metrics_file and metrics_file.exists():
        metrics.update(read_metrics_json(metrics_file))
    if report_file and report_file.exists():
        report = read_classification_report(report_file)
        metrics.update(_metrics_from_classification_report(report))
        per_class.update(_per_class_from_report(report))
    if trainer_state_file and trainer_state_file.exists():
        metrics.update(_metrics_from_trainer_state(read_trainer_state(trainer_state_file)))
    if log_file and log_file.exists() and not metrics:
        metrics.update(_metrics_from_log(log_file))

    record_notes = list(notes or [])
    record_tags = list(tags or [])
    if tracker_run is not None:
        record_tags.append(f"source:{tracker_run.source}")
        record_notes.append(f"Ingested from {tracker_run.source} run.")

    record = ExperimentRecord(
        id=next_experiment_id(),
        name=name or str(metadata.get("name") or "training_run"),
        kind=str(kind or metadata.get("kind") or "unknown"),  # type: ignore[arg-type]
        model=model or metadata.get("model"),
        dataset=dataset or metadata.get("dataset"),
        config_path=(config_file.as_posix() if config_file else metadata.get("config_path")),
        status=status,  # type: ignore[arg-type]
        metrics=metrics,
        per_class=per_class,
        duration_sec=metrics.pop("duration_sec", None),
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        notes=record_notes,
        tags=record_tags,
        artifacts=ExperimentArtifacts(
            run_dir=run_dir.as_posix() if run_dir.exists() else None,
            log_path=log_file.as_posix() if log_file else None,
            metrics_path=metrics_file.as_posix() if metrics_file else None,
            report_path=report_file.as_posix() if report_file else None,
            config_path=config_file.as_posix() if config_file else None,
            trainer_state_path=trainer_state_file.as_posix() if trainer_state_file else None,
        ),
    )
    save_experiment(record, allow_overwrite=False)
    return record


def _merge_tracker(
    metrics: dict[str, float], metadata: dict[str, Any], tracker_run: TrackerRun
) -> None:
    """Merge tracker metrics/params into the in-progress record fields.

    Tracker values are the base layer; explicit files (metrics.json, reports)
    merged afterwards take precedence.
    """
    for key, value in tracker_run.metrics.items():
        metrics.setdefault(_normalize_metric_key(key), value)
    if not metadata.get("model"):
        metadata["model"] = _first_present(tracker_run.params, ("model", "model_name", "backbone"))
    if not metadata.get("dataset"):
        metadata["dataset"] = _first_present(
            tracker_run.params, ("dataset", "dataset_name", "data")
        )
    name = metadata.get("name")
    if (not name or name == "training_run") and tracker_run.name:
        metadata["name"] = _slug(tracker_run.name)
        if "baseline" in tracker_run.name.lower():
            metadata["kind"] = "baseline"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _find_first(run_dir: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    return None


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            name = value.get("name") or value.get("path")
            if isinstance(name, str):
                return name
    return None


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return slug


def _normalize_metric_key(key: str) -> str:
    normalized = key.removeprefix("eval_").removeprefix("validation_")
    return {"f1": "macro_f1", "f1_score": "macro_f1", "loss": "train_loss"}.get(
        normalized, normalized
    )


def _metrics_from_classification_report(report: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    macro = report.get("macro avg")
    weighted = report.get("weighted avg")
    if isinstance(macro, dict):
        value = macro.get("f1-score") or macro.get("f1")
        if isinstance(value, int | float):
            metrics["macro_f1"] = float(value)
        recall = macro.get("recall")
        if isinstance(recall, int | float):
            metrics["macro_recall"] = float(recall)
    if isinstance(weighted, dict):
        value = weighted.get("f1-score") or weighted.get("f1")
        if isinstance(value, int | float):
            metrics["weighted_f1"] = float(value)
    accuracy = report.get("accuracy")
    if isinstance(accuracy, int | float):
        metrics["accuracy"] = float(accuracy)
    return metrics


def _per_class_from_report(report: dict[str, Any]) -> dict[str, PerClassMetrics]:
    per_class: dict[str, PerClassMetrics] = {}
    skipped = {"accuracy", "macro avg", "weighted avg", "micro avg", "samples avg"}
    for label, values in report.items():
        if label in skipped or not isinstance(values, dict):
            continue
        per_class[str(label)] = PerClassMetrics(
            precision=_float_or_none(values.get("precision")),
            recall=_float_or_none(values.get("recall")),
            f1=_float_or_none(values.get("f1-score") or values.get("f1")),
            support=_int_or_none(values.get("support")),
        )
    return per_class


def _metrics_from_trainer_state(state: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    history = state.get("log_history")
    if not isinstance(history, list):
        return metrics
    for item in history:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if isinstance(value, int | float) and not isinstance(value, bool):
                normalized = _normalize_metric_key(key)
                if normalized in {"train_loss", "val_loss", "eval_loss", "macro_f1", "accuracy"}:
                    metrics[normalized.replace("eval_loss", "val_loss")] = float(value)
    return metrics


def _metrics_from_log(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    metrics: dict[str, float] = {}
    for key, raw in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(-?\d+(?:\.\d+)?)", text):
        normalized = _normalize_metric_key(key)
        if normalized in {"macro_f1", "accuracy", "train_loss", "val_loss", "loss_std"}:
            metrics[normalized] = float(raw)
    return metrics


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value)
    return None
