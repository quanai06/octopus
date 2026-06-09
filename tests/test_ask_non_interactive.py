from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.storage.state_store import load_state

runner = CliRunner()


def _answers() -> dict:
    return {
        "project_name": "Vietnamese Emotion Classifier",
        "project_type": "machine learning",
        "task_type": "text_classification",
        "input_type": "text",
        "output_type": "emotion_label",
        "main_metric": "macro_f1",
        "target_score": 0.82,
        "has_class_imbalance": True,
        "runtime": ["claude", "codex"],
        "compute": {"has_gpu": False, "environment": "local"},
    }


def test_ask_from_file_sets_state(tmp_project):
    runner.invoke(app, ["init", "--force"])
    Path("answers.yaml").write_text(yaml.safe_dump(_answers()), encoding="utf-8")

    result = runner.invoke(app, ["ask", "--from", "answers.yaml"])

    assert result.exit_code == 0, result.output
    state = load_state()
    assert state.project_name == "Vietnamese Emotion Classifier"
    assert state.task_type == "text_classification"
    assert state.main_metric == "macro_f1"
    assert state.target_score == 0.82
    assert state.compute.environment == "local"
    assert state.runtime == ["claude", "codex"]


def test_ask_from_file_rejects_unknown_keys(tmp_project):
    runner.invoke(app, ["init", "--force"])
    answers = _answers()
    answers["dataset"] = {"train": "train.csv"}
    Path("answers.yaml").write_text(yaml.safe_dump(answers), encoding="utf-8")

    result = runner.invoke(app, ["ask", "--from", "answers.yaml"])

    assert result.exit_code == 1
    assert "unknown top-level" in result.output
    assert "dataset" in result.output


def test_ask_from_file_infers_ml_from_ml_fields(tmp_project):
    runner.invoke(app, ["init", "--force"])
    answers = _answers()
    answers.pop("project_type")
    Path("answers.yaml").write_text(yaml.safe_dump(answers), encoding="utf-8")

    result = runner.invoke(app, ["ask", "--from", "answers.yaml"])

    assert result.exit_code == 0, result.output
    assert load_state().project_type == "machine learning"


def test_ask_schema_prints_example(tmp_project):
    result = runner.invoke(app, ["ask", "--schema"])

    assert result.exit_code == 0
    assert "project_name:" in result.output
    assert "compute:" in result.output


def test_ask_from_file_merges_onto_existing(tmp_project):
    runner.invoke(app, ["init", "--force"])
    Path("a1.yaml").write_text(yaml.safe_dump(_answers()), encoding="utf-8")
    runner.invoke(app, ["ask", "--from", "a1.yaml"])
    # Second partial file should only change the metric, keep the rest.
    Path("a2.yaml").write_text(yaml.safe_dump({"main_metric": "accuracy"}), encoding="utf-8")

    result = runner.invoke(app, ["ask", "--from", "a2.yaml"])

    assert result.exit_code == 0
    state = load_state()
    assert state.main_metric == "accuracy"
    assert state.project_name == "Vietnamese Emotion Classifier"  # preserved


def test_ask_from_file_missing_file_exits(tmp_project):
    runner.invoke(app, ["init", "--force"])
    result = runner.invoke(app, ["ask", "--from", "nope.yaml"])
    assert result.exit_code == 1


def test_ask_from_file_powers_baseline_flow(tmp_project):
    # End-to-end headless: ask --from -> plan/ml-plan/tasks -> context, no TTY needed.
    runner.invoke(app, ["init", "--force"])
    Path("answers.yaml").write_text(yaml.safe_dump(_answers()), encoding="utf-8")
    assert runner.invoke(app, ["ask", "--from", "answers.yaml"]).exit_code == 0
    for cmd in (["plan", "--force"], ["ml-plan", "--force"], ["tasks", "--force"]):
        assert runner.invoke(app, cmd).exit_code == 0
    ctx = runner.invoke(app, ["context", "--task", "train the baseline", "--profile", "training"])
    assert ctx.exit_code == 0
    assert Path(".octopus/context/current_context.md").exists()
