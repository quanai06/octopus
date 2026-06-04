from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _init_project():
    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0


def test_exp_log_writes_yaml(tmp_project):
    _init_project()

    result = runner.invoke(
        app,
        [
            "exp",
            "log",
            "--name",
            "phobert_weighted_loss",
            "--model",
            "phobert-base",
            "--dataset",
            "vietnamese_emotion",
            "--metric",
            "macro_f1=0.72",
            "--metric",
            "fear_recall=0.51",
            "--note",
            "Improved minority recall but overfit after epoch 3",
        ],
    )

    assert result.exit_code == 0
    path = Path(".octopus/experiments/exp_001.yaml")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["id"] == "exp_001"
    assert data["name"] == "phobert_weighted_loss"
    assert data["model"] == "phobert-base"
    assert data["dataset"] == "vietnamese_emotion"
    assert data["status"] == "completed"
    assert data["metrics"]["macro_f1"] == 0.72
    assert data["metrics"]["fear_recall"] == 0.51
    assert "Improved minority recall" in data["notes"]
    assert "add early stopping" in data["next_ideas"]
    assert "try class weights or balanced sampling" in data["next_ideas"]


def test_exp_init_creates_index_placeholder_and_report(tmp_project):
    _init_project()

    result = runner.invoke(app, ["exp", "init"])

    assert result.exit_code == 0
    assert Path(".octopus/experiments/index.yaml").exists()
    assert Path(".octopus/experiments/exp_001.yaml").exists()
    assert Path(".octopus/reports/experiment_report.md").exists()
    data = yaml.safe_load(Path(".octopus/experiments/exp_001.yaml").read_text())
    assert data["status"] == "planned"


def test_exp_list_shows_logged_experiment(tmp_project):
    _init_project()
    runner.invoke(app, ["exp", "log", "--name", "baseline", "--metric", "macro_f1=0.5"])

    result = runner.invoke(app, ["exp", "list"])

    assert result.exit_code == 0
    assert "exp_001" in result.output
    assert "baseline" in result.output
    assert "macro_f1=0.5" in result.output


def test_exp_suggest_detects_unchanged_metric(tmp_project):
    _init_project()
    for index, score in enumerate([0.61, 0.615, 0.612], start=1):
        runner.invoke(
            app,
            [
                "exp",
                "log",
                "--name",
                f"run_{index}",
                "--metric",
                f"macro_f1={score}",
            ],
        )

    result = runner.invoke(app, ["exp", "suggest"])

    assert result.exit_code == 0
    assert "macro_f1 has barely changed" in result.output


def test_exp_compare_shows_best_and_warning(tmp_project):
    _init_project()
    runner.invoke(
        app,
        [
            "exp",
            "log",
            "--name",
            "baseline",
            "--model",
            "TF-IDF + SVM",
            "--metric",
            "macro_f1=0.53",
            "--metric",
            "accuracy=0.70",
            "--metric",
            "fear_recall=0.31",
        ],
    )
    runner.invoke(
        app,
        [
            "exp",
            "log",
            "--name",
            "weighted_loss",
            "--model",
            "PhoBERT + class weights",
            "--metric",
            "macro_f1=0.76",
            "--metric",
            "accuracy=0.80",
            "--metric",
            "fear_recall=0.59",
        ],
    )

    result = runner.invoke(app, ["exp", "compare", "--metric", "macro_f1"])

    assert result.exit_code == 0
    assert "Best experiment by macro_f1" in result.output
    assert "weighted_loss" in result.output
    assert "+0.230" in result.output
    assert "fear_recall is still low" in result.output


def test_exp_diagnose_detects_accuracy_macro_gap(tmp_project):
    _init_project()
    runner.invoke(
        app,
        [
            "exp",
            "log",
            "--name",
            "high_accuracy_low_f1",
            "--metric",
            "accuracy=0.91",
            "--metric",
            "macro_f1=0.62",
            "--metric",
            "fear_recall=0.34",
        ],
    )

    result = runner.invoke(app, ["exp", "diagnose", "--exp", "exp_001"])

    assert result.exit_code == 0
    assert "Accuracy is high but macro F1 is much lower" in result.output
    assert "Check class distribution" in result.output


def test_exp_report_writes_markdown(tmp_project):
    _init_project()
    runner.invoke(app, ["exp", "log", "--name", "baseline", "--metric", "macro_f1=0.5"])

    result = runner.invoke(app, ["exp", "report"])

    assert result.exit_code == 0
    report = Path(".octopus/reports/experiment_report.md")
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "# Experiment Report" in content
    assert "## Experiment Timeline" in content


def test_exp_log_rejects_invalid_metric(tmp_project):
    _init_project()

    result = runner.invoke(app, ["exp", "log", "--name", "bad", "--metric", "macro_f1"])

    assert result.exit_code == 1
    assert "Use key=value" in result.output


def test_exp_log_blocks_main_model_before_baseline_for_ml_project(tmp_project):
    _init_project()
    write_state(sample_ml_state())

    result = runner.invoke(
        app,
        [
            "exp",
            "log",
            "--name",
            "phobert_main",
            "--model",
            "phobert-base",
            "--metric",
            "macro_f1=0.62",
        ],
    )

    assert result.exit_code == 1
    assert "Main model experiment blocked" in result.output
    assert "octopus exp log --kind baseline" in result.output
    assert not Path(".octopus/experiments/exp_001.yaml").exists()
