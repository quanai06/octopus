import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _init_project() -> None:
    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    write_state(sample_ml_state(target_score=0.72))


def _write_run_dir() -> Path:
    run_dir = Path("runs/E001")
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(
            {
                "macro_f1": 0.71,
                "accuracy": 0.84,
                "val_loss": 0.62,
                "train_loss": 0.31,
                "duration_sec": 8640,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "classification_report.json").write_text(
        json.dumps(
            {
                "fear": {"precision": 0.50, "recall": 0.41, "f1-score": 0.45, "support": 120},
                "joy": {"precision": 0.88, "recall": 0.91, "f1-score": 0.89, "support": 920},
                "macro avg": {"precision": 0.68, "recall": 0.65, "f1-score": 0.71},
                "accuracy": 0.84,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "config.yaml").write_text(
        "model: phobert-base\ndataset: vie_emotion_v1\n",
        encoding="utf-8",
    )
    return run_dir


def test_exp_ingest_creates_e001_and_updates_index(tmp_project):
    _init_project()
    run_dir = _write_run_dir()

    result = runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir)])

    assert result.exit_code == 0
    path = Path(".octopus/experiments/E001.yaml")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["experiment_id"] == "E001"
    assert data["metrics"]["macro_f1"] == 0.71
    assert data["per_class"]["fear"]["recall"] == 0.41
    index = yaml.safe_load(Path(".octopus/experiments/index.yaml").read_text(encoding="utf-8"))
    assert index["latest_id"] == "E001"
    assert index["best_experiment_id"] == "E001"


def test_exp_analyze_detects_minority_recall_and_writes_report(tmp_project):
    _init_project()
    run_dir = _write_run_dir()
    runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline"])

    result = runner.invoke(app, ["exp", "analyze", "E001"])

    assert result.exit_code == 0
    report = Path(".octopus/reports/training_review_E001.md")
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "## 4. Diagnosis" in content
    assert "class_imbalance" in content
    assert "fear.recall=0.41" in content
    assert Path(".octopus/memory/experiments.md").exists()


def test_exp_next_recommends_class_imbalance_direction(tmp_project):
    _init_project()
    run_dir = _write_run_dir()
    runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline"])
    runner.invoke(app, ["exp", "analyze", "E001"])

    result = runner.invoke(app, ["exp", "next", "--top-k", "3"])

    assert result.exit_code == 0
    data = yaml.safe_load(Path(".octopus/plans/next_steps.yaml").read_text(encoding="utf-8"))
    first = data["directions"][0]
    assert first["direction_id"] == "D1"
    assert "minority recall" in first["title"].lower()
    assert first["recommendation"] == "recommended"
    assert Path(".octopus/plans/next_steps.md").exists()


def test_exp_choose_and_context_direction(tmp_project):
    _init_project()
    run_dir = _write_run_dir()
    runner.invoke(app, ["exp", "ingest", "--run-dir", str(run_dir), "--kind", "baseline"])
    runner.invoke(app, ["exp", "next"])
    Path("src").mkdir()
    Path("src/train.py").write_text(
        "class_weight = None\nsampler = None\nmetrics = ['macro_f1']\n",
        encoding="utf-8",
    )
    Path(".env").write_text("SECRET_TOKEN=abc", encoding="utf-8")
    Path("data").mkdir()
    Path("data/train.csv").write_text("text,label\nsecret,row\n", encoding="utf-8")

    choose = runner.invoke(app, ["exp", "choose", "D1"])
    context = runner.invoke(app, ["context", "--direction", "D1", "--target", "codex"])

    assert choose.exit_code == 0
    assert context.exit_code == 0
    assert Path(".octopus/plans/selected_direction.yaml").exists()
    content = Path(".octopus/context/current_context.md").read_text(encoding="utf-8")
    assert "## 2. Selected Direction" in content
    assert "## 11. Relevant Code Context" in content
    assert "src/train.py" in content
    assert "SECRET_TOKEN" not in content
    assert "secret,row" not in content


def test_runtime_sync_mentions_training_loop_files(tmp_project):
    _init_project()

    result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    claude = Path("CLAUDE.md").read_text(encoding="utf-8")
    assert ".octopus/context/current_context.md" in agents
    assert ".octopus/plans/selected_direction.yaml" in agents
    assert "Follow the selected direction only" in agents
    assert "Implement only the selected direction" in claude
