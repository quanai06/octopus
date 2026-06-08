import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.experiments.trackers import (
    TRACKER_MLFLOW,
    TRACKER_TENSORBOARD,
    TRACKER_WANDB,
    detect_tracker,
    load_tracker_run,
)
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _make_mlflow_run(root: Path) -> Path:
    run = root / "mlruns" / "0" / "abc123"
    (run / "metrics").mkdir(parents=True)
    (run / "params").mkdir(parents=True)
    # Append-only "<timestamp> <value> <step>"; the last line is the final value.
    (run / "metrics" / "macro_f1").write_text(
        "1700000000000 0.55 0\n1700000000001 0.71 1\n", encoding="utf-8"
    )
    (run / "metrics" / "accuracy").write_text("1700000000001 0.84 1\n", encoding="utf-8")
    (run / "params" / "model").write_text("phobert-base", encoding="utf-8")
    (run / "params" / "dataset").write_text("vie_emotion", encoding="utf-8")
    (run / "meta.yaml").write_text("run_name: baseline_run\n", encoding="utf-8")
    return run


def _make_wandb_run(root: Path) -> Path:
    run = root / "wandb" / "run-20260101_000000-xyz" / "files"
    run.mkdir(parents=True)
    (run / "wandb-summary.json").write_text(
        json.dumps({"macro_f1": 0.7, "accuracy": 0.83, "_runtime": 99, "_step": 4}),
        encoding="utf-8",
    )
    (run / "config.yaml").write_text(
        yaml.safe_dump(
            {"lr": {"value": 2e-5}, "model": {"value": "phobert"}, "_wandb": {"value": {}}}
        ),
        encoding="utf-8",
    )
    return run.parent  # point --run-dir at the run folder, summary is under files/


# --- detection -------------------------------------------------------------


def test_detect_mlflow(tmp_path):
    run = _make_mlflow_run(tmp_path)
    assert detect_tracker(run) == TRACKER_MLFLOW


def test_detect_wandb(tmp_path):
    run = _make_wandb_run(tmp_path)
    assert detect_tracker(run) == TRACKER_WANDB


def test_detect_tensorboard(tmp_path):
    run = tmp_path / "tb"
    run.mkdir()
    (run / "events.out.tfevents.1700000000.host").write_text("", encoding="utf-8")
    assert detect_tracker(run) == TRACKER_TENSORBOARD


def test_detect_none_for_plain_dir(tmp_path):
    assert detect_tracker(tmp_path) is None


# --- parsing ---------------------------------------------------------------


def test_load_mlflow_uses_last_metric_value_and_params(tmp_path):
    run = _make_mlflow_run(tmp_path)
    tracker_run = load_tracker_run(run)
    assert tracker_run is not None
    assert tracker_run.source == TRACKER_MLFLOW
    assert tracker_run.metrics["macro_f1"] == 0.71  # last line wins
    assert tracker_run.metrics["accuracy"] == 0.84
    assert tracker_run.params["model"] == "phobert-base"
    assert tracker_run.name == "baseline_run"


def test_load_wandb_skips_internal_keys(tmp_path):
    run = _make_wandb_run(tmp_path)
    tracker_run = load_tracker_run(run)
    assert tracker_run is not None
    assert tracker_run.source == TRACKER_WANDB
    assert tracker_run.metrics == {"macro_f1": 0.7, "accuracy": 0.83}
    assert tracker_run.params["model"] == "phobert"


def test_tracker_none_disables_detection(tmp_path):
    run = _make_mlflow_run(tmp_path)
    assert load_tracker_run(run, tracker="none") is None


# --- end to end through the CLI --------------------------------------------


def test_ingest_mlflow_run_through_cli(tmp_project):
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    write_state(sample_ml_state())
    run = _make_mlflow_run(tmp_project)

    result = runner.invoke(app, ["exp", "ingest", "--run-dir", str(run), "--kind", "baseline"])

    assert result.exit_code == 0, result.output
    record = yaml.safe_load(Path(".octopus/experiments/E001.yaml").read_text(encoding="utf-8"))
    assert record["metrics"]["macro_f1"] == 0.71
    assert record["model"] == "phobert-base"
    assert "source:mlflow" in record["tags"]


def test_invalid_tracker_value_exits(tmp_project):
    runner.invoke(app, ["init", "--force"])
    result = runner.invoke(app, ["exp", "ingest", "--run-dir", ".", "--tracker", "bogus"])
    assert result.exit_code == 1
    assert "tracker" in result.output.lower()
