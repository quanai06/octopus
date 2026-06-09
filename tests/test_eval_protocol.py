from pathlib import Path

from typer.testing import CliRunner

from octopus.cli.main import app
from octopus.planners.ml_rules import evaluation_protocol_for
from tests.helpers import sample_ml_state, write_state

runner = CliRunner()


def _render(task_type: str, main_metric: str) -> tuple[str, str]:
    runner.invoke(app, ["init", "--force"])
    write_state(sample_ml_state(task_type=task_type, main_metric=main_metric))
    runner.invoke(app, ["plan", "--force"])
    runner.invoke(app, ["ml-plan", "--force"])
    runner.invoke(app, ["tasks", "--force"])
    runner.invoke(app, ["context", "--task", "train the baseline", "--profile", "training"])
    return (
        Path("data_strategy.md").read_text(encoding="utf-8"),
        Path(".octopus/context/current_context.md").read_text(encoding="utf-8"),
    )


def test_protocol_selection_is_data_type_aware():
    assert "StratifiedKFold" in " ".join(evaluation_protocol_for("text_classification"))
    assert "StratifiedKFold" in " ".join(evaluation_protocol_for("image_classification"))
    assert "KFold" in " ".join(evaluation_protocol_for("regression"))
    assert "TimeSeriesSplit" in " ".join(evaluation_protocol_for("forecasting"))
    assert "Recall@k" in " ".join(evaluation_protocol_for("rag"))
    assert "time-aware" in " ".join(evaluation_protocol_for("recommendation"))
    # Unknown task falls back to the generic k-fold default.
    assert "k-fold cross-validation" in " ".join(evaluation_protocol_for("something_new"))


def test_classification_baseline_uses_stratified_kfold(tmp_project):
    ds, ctx = _render("text_classification", "macro_f1")
    assert "## Split & Cross-Validation" in ds
    assert "StratifiedKFold" in ds
    assert "mean ± std" in ds
    assert "canonical cleaned dataset" in ds
    assert "split/fold" in ds
    # The protocol must reach the agent's working context, not just the doc.
    assert "StratifiedKFold" in ctx
    assert "canonical cleaned dataset" in ctx


def test_forecasting_baseline_uses_timeseries_split(tmp_project):
    ds, ctx = _render("forecasting", "RMSE")
    assert "TimeSeriesSplit" in ds
    assert "Never shuffle" in ds
    assert "temporal fold boundaries" in ds
    assert "TimeSeriesSplit" in ctx


def test_rag_baseline_uses_fixed_query_eval_set(tmp_project):
    ds, ctx = _render("rag", "Recall@k")
    assert "fixed labeled query" in ds.lower()
    assert "Recall@k" in ds
    assert "chunking grid" in ds
    assert "k=3/5/10/20" in ds
    assert "rerank a recorded candidate pool" in ds
    assert "BM25" in ctx
    assert "top-k" in ctx


def test_experiment_plan_baseline_mentions_cross_validation(tmp_project):
    _render("text_classification", "macro_f1")
    plan = Path("experiment_plan.md").read_text(encoding="utf-8")
    assert "cross-validat" in plan.lower()
    assert "mean ± std" in plan
    assert "cleaned-data manifest" in plan
