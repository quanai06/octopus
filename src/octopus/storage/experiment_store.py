from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import EXPERIMENT_INDEX, EXPERIMENT_REPORT_MD, EXPERIMENTS_DIR, REPORTS_DIR
from octopus.core.schemas import ExperimentRecord


def experiment_path(experiment_id: str) -> Path:
    return EXPERIMENTS_DIR / f"{experiment_id}.yaml"


def list_experiments() -> list[ExperimentRecord]:
    if not EXPERIMENTS_DIR.exists():
        return []
    records: list[ExperimentRecord] = []
    for path in sorted(EXPERIMENTS_DIR.glob("exp_*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        records.append(ExperimentRecord.model_validate(data))
    return records


def next_experiment_id() -> str:
    max_id = 0
    for record in list_experiments():
        try:
            max_id = max(max_id, int(record.id.removeprefix("exp_")))
        except ValueError:
            continue
    return f"exp_{max_id + 1:03d}"


def save_experiment(record: ExperimentRecord) -> Path:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = record.model_dump(mode="json")
    path = experiment_path(record.id)
    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False))
    write_experiment_index()
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
            name="first_experiment",
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
    payload = {
        "version": "0.1.0",
        "experiments": [
            {
                "id": record.id,
                "name": record.name,
                "kind": record.kind,
                "model": record.model,
                "dataset": record.dataset,
                "status": record.status,
                "created_at": record.created_at.isoformat(),
                "path": experiment_path(record.id).as_posix(),
                "metrics": record.metrics,
            }
            for record in records
        ],
    }
    atomic_write_text(EXPERIMENT_INDEX, yaml.safe_dump(payload, sort_keys=False))
    return EXPERIMENT_INDEX


def get_experiment(experiment_id: str) -> ExperimentRecord:
    path = experiment_path(experiment_id)
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ExperimentRecord.model_validate(data)
