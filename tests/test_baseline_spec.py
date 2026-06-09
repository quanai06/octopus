from pathlib import Path

import yaml
from typer.testing import CliRunner

from octopus.cli.main import app
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def test_baseline_spec_detects_fixed_split_files(tmp_project):
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    for name in ("train_nor_811.xlsx", "valid_nor_811.xlsx", "test_nor_811.xlsx"):
        Path(name).write_text("", encoding="utf-8")
    write_state(
        sample_ml_state(
            dataset_size_note=(
                "fixed train/valid/test files: train_nor_811.xlsx, "
                "valid_nor_811.xlsx, test_nor_811.xlsx"
            )
        )
    )

    result = runner.invoke(app, ["baseline-spec", "--force"])

    assert result.exit_code == 0, result.output
    spec = yaml.safe_load(Path("baseline_spec.yaml").read_text(encoding="utf-8"))
    assert spec["task"] == "text_classification"
    assert spec["metric"] == "macro_f1"
    assert spec["data"]["fixed_split"] is True
    assert spec["data"]["train"] == "train_nor_811.xlsx"
    assert spec["data"]["valid"] == "valid_nor_811.xlsx"
    assert spec["data"]["test"] == "test_nor_811.xlsx"
    assert spec["baseline"]["model"] == "tfidf_logreg"
    assert spec["baseline"]["final_train"] == "train_valid"
    assert spec["artifacts"]["save_predictions"] is True
