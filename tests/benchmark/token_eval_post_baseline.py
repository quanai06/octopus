"""Post-baseline token benchmark for a stacking/ensemble upgrade.

This benchmark simulates the next stage after a completed baseline exists:
plan a disciplined multi-model stacking upgrade without training. It creates
Octopus project state, logs a completed baseline, writes a selected stacking
direction, builds direction context, then compares prompt-only grounding vs
Octopus grounding.

Run from the repository root:

    python tests/benchmark/token_eval_post_baseline.py
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from octopus.cli.commands.context import build_current_context
from octopus.cli.commands.init import init_project
from octopus.cli.commands.ml_plan import generate_ml_plan
from octopus.cli.commands.plan import generate_plan
from octopus.cli.commands.tasks import generate_tasks
from octopus.context.builder import build_direction_context
from octopus.context.token_estimator import ENCODING, estimate_tokens
from octopus.core.files import atomic_write_text
from octopus.core.paths import (
    BASELINE_PROFILE_MD,
    BEST_RUNS_MD,
    EXPERIMENT_MEMORY_MD,
    NEXT_STEPS_MD,
    NEXT_STEPS_YAML,
)
from octopus.core.schemas import ExperimentRecord, NextDirection, PerClassMetrics
from octopus.experiments.baseline_profile import profile_baseline, write_baseline_profile_md
from octopus.experiments.selection import choose_direction
from octopus.storage.experiment_store import save_experiment
from octopus.storage.state_store import save_state
from tests.benchmark.token_eval_datasets import (
    OCTOPUS_PROMPT,
    PLANNING_DOCS,
    Scenario,
    build_scenarios,
)


STACKING_PROMPT = (
    "The baseline is already logged. Plan the next upgrade: evaluate several candidate "
    "models and build a stacking ensemble only with out-of-fold predictions. Do not train "
    "now. Keep the existing train/validation/test split frozen, never tune on the test set, "
    "make each base model a separately logged candidate run, and use validation/OOF data "
    "for the meta-model. Produce an upgrade plan and a stacking script skeleton, then STOP."
)


@dataclass(frozen=True)
class PostBaselineRow:
    scenario: str
    a_input_tokens: int
    b_input_tokens: int
    saving_pct: float
    deliverable_tokens: int
    output_dir: Path


def _baseline_record(scenario: Scenario) -> ExperimentRecord:
    if scenario.key == "ML":
        return ExperimentRecord(
            id="E001",
            experiment_id="E001",
            name="tfidf_logreg_baseline",
            kind="baseline",
            model="TF-IDF + Logistic Regression",
            dataset="tests/datasets/vsmec",
            metrics={"macro_f1": 0.43, "accuracy": 0.55, "val_loss": 1.18},
            per_class={
                "Enjoyment": PerClassMetrics(recall=0.61, f1=0.58, support=1935),
                "Sadness": PerClassMetrics(recall=0.34, f1=0.36, support=1139),
                "Fear": PerClassMetrics(recall=0.25, f1=0.28, support=441),
                "Surprise": PerClassMetrics(recall=0.21, f1=0.23, support=334),
            },
            notes=["CPU baseline complete", "minority recall remains weak"],
            status="completed",
        )
    if scenario.key == "DL":
        return ExperimentRecord(
            id="E001",
            experiment_id="E001",
            name="mobilenet_no_aug_baseline",
            kind="baseline",
            model="MobileNetV2 frozen backbone",
            dataset="tests/datasets/alpaca-dataset/dataset",
            metrics={"macro_f1": 0.72, "accuracy": 0.76, "val_loss": 0.64, "train_loss": 0.42},
            per_class={
                "alpaca": PerClassMetrics(recall=0.69, f1=0.70, support=142),
                "not alpaca": PerClassMetrics(recall=0.78, f1=0.75, support=185),
            },
            notes=["no augmentation baseline complete", "small dataset"],
            status="completed",
        )
    return ExperimentRecord(
        id="E001",
        experiment_id="E001",
        name="bm25_retrieval_baseline",
        kind="baseline",
        model="BM25",
        dataset="tests/datasets/wikiqa",
        metrics={"Recall@k": 0.58, "MRR": 0.39, "source_hit_rate": 0.58},
        notes=["retrieval-only baseline complete", "generation not evaluated"],
        status="completed",
    )


def _stacking_direction(scenario: Scenario) -> NextDirection:
    if scenario.key == "RAG":
        title = "Hybrid lexical retriever stack with reciprocal rank fusion"
        expected = "Improve source-hit / Recall@k while keeping retrieval evaluation fixed."
        files = ["retriever", "bm25", "tfidf", "rank_fusion", "eval"]
        edit = ["retriever", "retrieval eval", "rank fusion config"]
        guardrails = [
            "Keep train/dev/test query splits fixed.",
            "Evaluate retrieval before generation.",
            "Do not tune fusion weights on the test set.",
            "Log each retriever variant as a candidate run before comparing fusion.",
        ]
        stop = "Fusion skeleton is ready; no retrieval run has been executed."
    else:
        title = "Stack validated candidate models with out-of-fold predictions"
        expected = "Combine complementary model errors after baseline and candidate runs exist."
        files = ["train", "evaluate", "metrics", "oof", "stacking", "model"]
        edit = ["stacking pipeline", "candidate registry", "meta-model eval"]
        guardrails = [
            "Freeze the existing train/validation/test split.",
            "Train/log each base model as a separate candidate run before stacking.",
            "Fit the meta-model only on OOF/validation predictions.",
            "Do not tune on the test set.",
        ]
        stop = "Stacking skeleton is ready; no candidate or ensemble training has run."
    return NextDirection(
        direction_id="D1",
        title=title,
        priority=6,
        recommendation="optional",
        rationale=(
            "A baseline exists, so an ensemble can be planned, but it must be staged as "
            "candidate runs plus leakage-safe stacking rather than one uncontrolled jump."
        ),
        evidence=[
            "completed baseline E001 exists",
            "stacking requires OOF predictions or a held-out validation protocol",
            "test set must remain untouched until final reporting",
        ],
        confidence="medium",
        risk="medium",
        cost="medium",
        expected_impact=expected,
        files_to_read=files,
        files_to_edit=edit,
        commands_to_run=["pytest -q"],
        guardrails=guardrails,
        stop_condition=stop,
    )


def _write_next_direction(direction: NextDirection) -> None:
    NEXT_STEPS_YAML.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "post-baseline stacking benchmark", "directions": [direction.model_dump(mode="json")]}
    atomic_write_text(NEXT_STEPS_YAML, yaml.safe_dump(payload, sort_keys=False))
    atomic_write_text(
        NEXT_STEPS_MD,
        "\n".join(
            [
                "# Next Steps - Post Baseline Stacking Benchmark",
                "",
                f"## {direction.direction_id} - {direction.title}",
                "",
                direction.rationale,
                "",
                "Guardrails:",
                *[f"- {item}" for item in direction.guardrails],
                "",
                "Stop condition:",
                direction.stop_condition or "Stop after skeleton.",
                "",
            ]
        ),
    )
    choose_direction(direction.direction_id)


def _write_code_context(scenario: Scenario) -> list[str]:
    src = Path("src")
    src.mkdir(exist_ok=True)
    if scenario.key == "ML":
        files = {
            "src/train_baseline.py": (
                "MODEL = 'tfidf_logreg'\nMETRIC = 'macro_f1'\n"
                "def load_vsmec(): pass\n"
                "def train_tfidf_logreg(): pass\n"
                "def evaluate_per_class_recall(): pass\n"
            ),
            "src/stacking.py": (
                "BASE_MODELS = ['tfidf_logreg', 'linear_svc', 'char_ngram_logreg']\n"
                "def build_oof_predictions(): pass\n"
                "def fit_meta_model_on_oof(): pass\n"
            ),
        }
    elif scenario.key == "DL":
        files = {
            "src/train_baseline.py": (
                "BACKBONE = 'mobilenet_v2'\nAUGMENTATION = False\n"
                "def build_dataloaders(): pass\n"
                "def evaluate_macro_f1(): pass\n"
            ),
            "src/stacking.py": (
                "BASE_MODELS = ['mobilenet_v2', 'resnet18', 'efficientnet_b0']\n"
                "def collect_oof_logits(): pass\n"
                "def train_meta_classifier(): pass\n"
            ),
        }
    else:
        files = {
            "src/retriever.py": (
                "def bm25_rank(question, candidates): pass\n"
                "def evaluate_recall_at_k(): pass\n"
            ),
            "src/rank_fusion.py": (
                "RETRIEVERS = ['bm25', 'tfidf_word', 'tfidf_char']\n"
                "def reciprocal_rank_fusion(rankings): pass\n"
                "def evaluate_source_hit_rate(): pass\n"
            ),
        }
    for rel, text in files.items():
        Path(rel).write_text(text, encoding="utf-8")
    return list(files)


def _deliverable(scenario: Scenario) -> tuple[str, str]:
    if scenario.key == "RAG":
        plan = f"""# Post-Baseline Upgrade Plan - WikiQA Retriever Fusion

Baseline: BM25 is logged as `E001`.

1. Keep WikiQA train/dev/test fixed.
2. Add candidate retrievers one at a time: BM25, word TF-IDF, character TF-IDF.
3. Persist rankings per retriever before fusion.
4. Add reciprocal-rank fusion as the only ensemble change.
5. Evaluate Recall@k, MRR, and source-hit rate on dev; reserve test for final reporting.
6. Do not evaluate generation in this step.
"""
        skeleton = '''"""Retriever-fusion skeleton for WikiQA.

This file is intentionally not executed by the benchmark.
"""

from pathlib import Path

DATA_DIR = Path("tests/datasets/wikiqa")
RETRIEVERS = ("bm25", "tfidf_word", "tfidf_char")
K_VALUES = (1, 3, 5, 10)


def load_rankings(split):
    # TODO: load or compute per-retriever rankings for each question.
    raise NotImplementedError


def reciprocal_rank_fusion(rankings, k=60):
    # TODO: combine rankings without looking at test labels.
    raise NotImplementedError


def evaluate_fusion(fused_rankings, labels):
    # TODO: Recall@k, MRR, source-hit rate.
    raise NotImplementedError
'''
        return plan, skeleton

    plan = f"""# Post-Baseline Upgrade Plan - {scenario.title} Stacking

Baseline: completed baseline `E001` exists for {scenario.title}.

1. Freeze the existing split and baseline preprocessing.
2. Train/log each base model as a separate candidate run in the future.
3. Generate out-of-fold predictions for each candidate model.
4. Fit a simple logistic-regression meta-model on OOF/validation predictions only.
5. Compare the stack against the best single candidate using macro-F1 and per-class recall.
6. Do not train any model in this benchmark; only write the skeleton.
"""
    skeleton = '''"""Leakage-safe stacking skeleton.

This file is intentionally not executed by the benchmark.
"""

from pathlib import Path

RUN_DIR = Path("runs")
SEED = 42


def load_candidate_predictions(candidate_run_dirs):
    # TODO: read validation/OOF predictions and labels from logged candidate runs.
    raise NotImplementedError


def validate_prediction_alignment(prediction_frames):
    # TODO: ensure sample ids, labels, and split ids match exactly.
    raise NotImplementedError


def fit_meta_model(oof_features, labels):
    # TODO: fit a simple regularized meta-classifier on OOF features only.
    raise NotImplementedError


def evaluate_stack(meta_model, features, labels):
    # TODO: macro-F1, per-class recall, confusion matrix.
    raise NotImplementedError
'''
    return plan, skeleton


def _setup_project(project_dir: Path, scenario: Scenario) -> tuple[int, int, int]:
    original = Path.cwd()
    os.chdir(project_dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            init_project(runtime="claude,codex", force=True)
            save_state(scenario.state)
            generate_plan(force=True)
            generate_ml_plan(force=True)
            generate_tasks(force=True)
            build_current_context(task="write baseline plan and script skeleton", profile="training")
            save_experiment(_baseline_record(scenario))
            write_baseline_profile_md(profile_baseline("E001"))
        _write_code_context(scenario)
        direction = _stacking_direction(scenario)
        _write_next_direction(direction)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build_direction_context(scenario.state, "D1", target="codex")

        manual_files = [
            *PLANNING_DOCS,
            BASELINE_PROFILE_MD.as_posix(),
            NEXT_STEPS_MD.as_posix(),
            NEXT_STEPS_YAML.as_posix(),
            EXPERIMENT_MEMORY_MD.as_posix(),
            BEST_RUNS_MD.as_posix(),
            "src/train_baseline.py",
        ]
        if scenario.key == "RAG":
            manual_files.extend(["src/retriever.py", "src/rank_fusion.py"])
        else:
            manual_files.append("src/stacking.py")
        manual_tokens = sum(
            estimate_tokens(Path(path).read_text(encoding="utf-8"))
            for path in manual_files
            if Path(path).exists()
        )
        context_tokens = estimate_tokens(
            Path(".octopus/context/current_context.md").read_text(encoding="utf-8")
        )
        profile_tokens = estimate_tokens(BASELINE_PROFILE_MD.read_text(encoding="utf-8"))
        return manual_tokens, context_tokens, profile_tokens
    finally:
        os.chdir(original)


def run_benchmark() -> list[PostBaselineRow]:
    root = Path(tempfile.mkdtemp(prefix="octopus-post-baseline-bench-"))
    rows: list[PostBaselineRow] = []
    for scenario in build_scenarios():
        project_dir = root / scenario.key.lower()
        project_dir.mkdir(parents=True)
        output_dir = project_dir / "stacking_deliverable"
        output_dir.mkdir()
        plan, skeleton = _deliverable(scenario)
        (output_dir / "upgrade_plan.md").write_text(plan, encoding="utf-8")
        (output_dir / "stacking_script_skeleton.py").write_text(skeleton, encoding="utf-8")

        manual_tokens, context_tokens, _ = _setup_project(project_dir, scenario)
        a_input = estimate_tokens(scenario.prompt) + estimate_tokens(STACKING_PROMPT)
        a_input += estimate_tokens(scenario.dataset_summary) + manual_tokens
        b_input = estimate_tokens(OCTOPUS_PROMPT) + estimate_tokens(STACKING_PROMPT)
        b_input += context_tokens
        deliverable_tokens = estimate_tokens(plan) + estimate_tokens(skeleton)

        rows.append(
            PostBaselineRow(
                scenario=scenario.key,
                a_input_tokens=a_input,
                b_input_tokens=b_input,
                saving_pct=round((a_input - b_input) / a_input * 100, 1),
                deliverable_tokens=deliverable_tokens,
                output_dir=output_dir,
            )
        )
    return rows


def format_markdown(rows: list[PostBaselineRow]) -> str:
    lines = [
        f"Tokenizer: `{ENCODING}`",
        "",
        "| Scenario | A prompt-only input | B Octopus direction input | Saving % | Upgrade plan+script output |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.scenario} | {row.a_input_tokens:,} | {row.b_input_tokens:,} | "
            f"{row.saving_pct:.1f}% | {row.deliverable_tokens:,} |"
        )
    lines.append("")
    lines.append("Generated deliverables:")
    for row in rows:
        lines.append(f"- {row.scenario}: `{row.output_dir}`")
    return "\n".join(lines)


def main() -> int:
    print(format_markdown(run_benchmark()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
