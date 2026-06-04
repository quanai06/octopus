from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import EXPERIMENT_INDEX, EXPERIMENT_REPORT_MD, EXPERIMENTS_DIR, REPORTS_DIR
from octopus.core.schemas import ExperimentRecord
from octopus.storage.state_store import load_state, state_exists


def experiment_path(experiment_id: str) -> Path:
    return EXPERIMENTS_DIR / f"{experiment_id}.yaml"


def _is_experiment_file(path: Path) -> bool:
    return path.name != "index.yaml" and (
        path.name.startswith("exp_") or path.stem.startswith("E")
    )


def load_experiment_index() -> dict[str, Any]:
    if not EXPERIMENT_INDEX.exists():
        return {}
    return yaml.safe_load(EXPERIMENT_INDEX.read_text(encoding="utf-8")) or {}


def list_experiments() -> list[ExperimentRecord]:
    if not EXPERIMENTS_DIR.exists():
        return []
    records: list[ExperimentRecord] = []
    for path in sorted(EXPERIMENTS_DIR.glob("*.yaml")):
        if not _is_experiment_file(path):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        records.append(ExperimentRecord.model_validate(data))
    return records


def next_legacy_experiment_id() -> str:
    max_id = 0
    for record in list_experiments():
        try:
            max_id = max(max_id, int(record.id.removeprefix("exp_")))
        except ValueError:
            continue
    return f"exp_{max_id + 1:03d}"


def next_experiment_id() -> str:
    max_id = 0
    index = load_experiment_index()
    latest = str(index.get("latest_id") or "")
    if latest.startswith("E"):
        try:
            max_id = max(max_id, int(latest.removeprefix("E")))
        except ValueError:
            pass
    for record in list_experiments():
        experiment_id = record.experiment_id or record.id
        if not experiment_id.startswith("E"):
            continue
        try:
            max_id = max(max_id, int(experiment_id.removeprefix("E")))
        except ValueError:
            continue
    return f"E{max_id + 1:03d}"


def save_experiment(record: ExperimentRecord, *, allow_overwrite: bool = True) -> Path:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = record.model_dump(mode="json")
    path = experiment_path(record.id)
    if path.exists() and not allow_overwrite:
        raise FileExistsError(path)
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False))
    update_experiment_index(record)
    return path


def latest_experiment() -> ExperimentRecord | None:
    records = list_experiments()
    return records[-1] if records else None


def initialize_experiment_tracking(*, create_placeholder: bool = True) -> list[Path]:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    if create_placeholder and not list(EXPERIMENTS_DIR.glob("exp_*.yaml")):
        placeholder = ExperimentRecord(
            id="exp_001",
            experiment_id="exp_001",
            name="first_experiment",
            kind="other",
            status="planned",
            notes=["replace this placeholder with the first real training run"],
            next_ideas=["run a reproducible baseline before advanced models"],
        )
        created.append(save_experiment(placeholder))
    else:
        write_experiment_index()
    if EXPERIMENT_INDEX.exists() and EXPERIMENT_INDEX not in created:
        created.append(EXPERIMENT_INDEX)

    if not EXPERIMENT_REPORT_MD.exists():
        atomic_write_text(
            EXPERIMENT_REPORT_MD,
            "# Experiment Report\n\n_No experiments completed yet._\n",
        )
        created.append(EXPERIMENT_REPORT_MD)
    return created


def write_experiment_index() -> Path:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    records = list_experiments()
    main_metric = _main_metric(records)
    completed = [record for record in records if record.status == "completed"]
    best = _best_by_metric(completed, main_metric)
    latest_phase_id = _latest_phase_id(records)
    payload = {
        "version": "0.2.5",
        "latest_id": latest_phase_id,
        "best_experiment_id": (best.experiment_id or best.id) if best else None,
        "main_metric": main_metric,
        "experiments": [
            {
                "id": record.experiment_id or record.id,
                "name": record.name,
                "kind": record.kind,
                "model": record.model,
                "dataset": record.dataset,
                "status": record.status,
                "created_at": record.created_at.isoformat(),
                "path": experiment_path(record.id).as_posix(),
                "main_metric_value": record.metrics.get(main_metric),
                "metrics": record.metrics,
            }
            for record in records
        ],
    }
    atomic_write_text(EXPERIMENT_INDEX, yaml.safe_dump(payload, sort_keys=False))
    return EXPERIMENT_INDEX


def update_experiment_index(record: ExperimentRecord | None = None) -> Path:
    return write_experiment_index()


def load_experiment(experiment_id: str) -> ExperimentRecord:
    path = experiment_path(experiment_id)
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ExperimentRecord.model_validate(data)


def get_experiment(experiment_id: str) -> ExperimentRecord:
    return load_experiment(experiment_id)


def _main_metric(records: list[ExperimentRecord]) -> str:
    if state_exists():
        try:
            state = load_state()
            if state.main_metric:
                return state.main_metric
        except FileNotFoundError:
            pass
    for preferred in ("macro_f1", "accuracy", "f1", "rmse", "mae"):
        if any(preferred in record.metrics for record in records):
            return preferred
    for record in records:
        if record.metrics:
            return next(iter(record.metrics))
    return "macro_f1"


def _best_by_metric(records: list[ExperimentRecord], metric: str) -> ExperimentRecord | None:
    candidates = [record for record in records if metric in record.metrics]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.metrics[metric])


def _latest_phase_id(records: list[ExperimentRecord]) -> str | None:
    latest = None
    for record in records:
        experiment_id = record.experiment_id or record.id
        if not experiment_id.startswith("E"):
            continue
        if latest is None or experiment_id > latest:
            latest = experiment_id
    return latest
