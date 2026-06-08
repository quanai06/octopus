"""Dataset-backed token benchmark for Octopus vs prompt-only Codex runs.

This benchmark intentionally stops at the fixed deliverable used by the eval:
write a baseline plan plus a baseline training/eval script skeleton, then stop.
It does not train any model.

Run from the repository root:

    python tests/benchmark/token_eval_datasets.py
"""

from __future__ import annotations

import contextlib
import csv
import io
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from octopus.cli.commands.context import build_current_context
from octopus.cli.commands.init import init_project
from octopus.cli.commands.ml_plan import generate_ml_plan
from octopus.cli.commands.plan import generate_plan
from octopus.cli.commands.tasks import generate_tasks
from octopus.context.token_estimator import ENCODING, estimate_tokens
from octopus.core.schemas import ComputeConfig, ProjectState
from octopus.storage.state_store import save_state


PLANNING_DOCS = [
    "requirements.md",
    "ml_design.md",
    "experiment_plan.md",
    "data_strategy.md",
    "compute_budget.md",
    "tasks.md",
]

OCTOPUS_PROMPT = (
    "This project uses Octopus. Run `octopus task next`, then read ONLY "
    "`.octopus/context/current_context.md` as your working context - do not paste any "
    "other planning docs. Follow it exactly: implement the baseline first, then stop "
    "after writing the baseline training-script skeleton (do not run it). Do not start "
    "the main model before a baseline, do not change the train/val/test split, and do "
    "not tune on the test set. The next step would be `octopus exp ingest --run-dir "
    "<run_dir>` then `octopus exp profile` - mention this but do not train now."
)


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    prompt: str
    state: ProjectState
    dataset_summary: str
    plan: str
    skeleton: str


@dataclass(frozen=True)
class BenchmarkRow:
    scenario: str
    a_input_tokens: int
    b_input_tokens: int
    saving_pct: float
    deliverable_tokens: int
    output_dir: Path


def _column_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    return index - 1


def _column_letters(ref: str) -> str:
    return "".join(char for char in ref if char.isalpha())


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(path) as archive:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", ns):
                strings.append("".join(t.text or "" for t in item.findall(".//a:t", ns)))

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", ns):
            values: list[str] = []
            for cell in row.findall("a:c", ns):
                cell_ref = cell.attrib.get("r", "A")
                idx = _column_index(_column_letters(cell_ref))
                while len(values) <= idx:
                    values.append("")

                value_node = cell.find("a:v", ns)
                value = "" if value_node is None or value_node.text is None else value_node.text
                if cell.attrib.get("t") == "s" and value:
                    value = strings[int(value)]
                values[idx] = value
            rows.append(values)
        return rows


def _vsmec_summary(dataset_root: Path) -> str:
    parts = []
    total = 0
    label_counts: Counter[str] = Counter()
    for split, name in [
        ("train", "train_nor_811.xlsx"),
        ("valid", "valid_nor_811.xlsx"),
        ("test", "test_nor_811.xlsx"),
    ]:
        rows = _read_xlsx_rows(dataset_root / name)
        header = rows[0]
        emotion_idx = header.index("Emotion")
        sentence_idx = header.index("Sentence")
        records = rows[1:]
        total += len(records)
        labels = Counter(row[emotion_idx] for row in records if len(row) > emotion_idx)
        label_counts.update(labels)
        example = next(row[sentence_idx] for row in records if len(row) > sentence_idx)
        parts.append(f"{split}: {len(records)} rows, labels={dict(labels)}, example={example!r}")
    return (
        "Dataset: tests/datasets/vsmec (Vietnamese Social Media Emotion Corpus). "
        f"Total rows={total}. Overall labels={dict(label_counts)}. Files: "
        + "; ".join(parts)
    )


def _alpaca_summary(dataset_root: Path) -> str:
    class_counts = {}
    for class_dir in sorted(path for path in dataset_root.iterdir() if path.is_dir()):
        class_counts[class_dir.name] = len([path for path in class_dir.iterdir() if path.is_file()])
    total = sum(class_counts.values())
    return (
        "Dataset: tests/datasets/alpaca-dataset/dataset. "
        f"Total images={total}. Class counts={class_counts}. JPEG binary classifier."
    )


def _wikiqa_summary(dataset_root: Path) -> str:
    parts = []
    for split, name in [
        ("train", "WikiQA-train.tsv"),
        ("dev", "WikiQA-dev.tsv"),
        ("test", "WikiQA-test.tsv"),
    ]:
        with (dataset_root / name).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = list(reader)
        questions = {row["QuestionID"] for row in rows}
        positives = sum(1 for row in rows if row["Label"] == "1")
        parts.append(
            f"{split}: {len(rows)} candidate rows, {len(questions)} questions, "
            f"{positives} positive answer sentences"
        )
    return (
        "Dataset: tests/datasets/wikiqa. Question-answer sentence relevance corpus. "
        + "; ".join(parts)
    )


def _ml_plan_and_skeleton(summary: str) -> tuple[str, str]:
    plan = f"""# Baseline Plan - VSMEC Emotion Classification

Dataset summary: {summary}

1. Load the provided train/valid/test XLSX files as fixed splits.
2. Use `Sentence` as text and `Emotion` as the target label.
3. Check missing values, label support, and exact duplicate sentences across splits.
4. Train only a TF-IDF + Logistic Regression baseline in the eventual run.
5. Report macro-F1, per-class recall, confusion matrix, and split-level duplicate warnings.
6. Stop after writing the script skeleton; do not train in this benchmark.
"""
    skeleton = '''"""TF-IDF + Logistic Regression baseline skeleton for VSMEC.

This file is intentionally not executed by the benchmark.
"""

from pathlib import Path

DATA_DIR = Path("tests/datasets/vsmec")
SPLITS = {
    "train": DATA_DIR / "train_nor_811.xlsx",
    "valid": DATA_DIR / "valid_nor_811.xlsx",
    "test": DATA_DIR / "test_nor_811.xlsx",
}
TEXT_COL = "Sentence"
LABEL_COL = "Emotion"
SEED = 42


def load_split(path):
    # TODO: read XLSX, validate columns, return text/label dataframe.
    raise NotImplementedError


def check_leakage(train_df, valid_df, test_df):
    # TODO: normalize text and report duplicate texts across fixed splits.
    raise NotImplementedError


def build_pipeline():
    # TODO: TfidfVectorizer + LogisticRegression(class_weight="balanced").
    raise NotImplementedError


def evaluate(model, x, y):
    # TODO: macro-F1, per-class recall, confusion matrix.
    raise NotImplementedError


def main():
    # TODO: load fixed splits, check leakage, fit on train, evaluate val/test.
    # Do not tune on test.
    raise NotImplementedError


if __name__ == "__main__":
    main()
'''
    return plan, skeleton


def _dl_plan_and_skeleton(summary: str) -> tuple[str, str]:
    plan = f"""# Baseline Plan - Alpaca Image Classification

Dataset summary: {summary}

1. Index image paths under the two class folders and create one fixed stratified split.
2. Persist the split manifest before any model training.
3. Use a pretrained MobileNetV2/ResNet18 transfer-learning baseline with no augmentation first.
4. Run only a smoke test in the eventual run before full baseline training.
5. Report macro-F1, per-class recall, confusion matrix, and class support.
6. Stop after writing the script skeleton; do not train in this benchmark.
"""
    skeleton = '''"""Transfer-learning baseline skeleton for the Alpaca image dataset.

This file is intentionally not executed by the benchmark.
"""

from pathlib import Path

DATA_DIR = Path("tests/datasets/alpaca-dataset/dataset")
SEED = 42
IMAGE_SIZE = 224
BATCH_SIZE = 8


def build_manifest():
    # TODO: collect image paths and labels from class folders.
    raise NotImplementedError


def make_fixed_split(manifest):
    # TODO: stratified train/val/test split; save manifest for reuse.
    raise NotImplementedError


def build_model(num_classes):
    # TODO: load pretrained MobileNetV2/ResNet18, freeze backbone first.
    raise NotImplementedError


def smoke_test(model, dataloader):
    # TODO: run one tiny forward/backward pass before real training.
    raise NotImplementedError


def evaluate(model, dataloader):
    # TODO: macro-F1 and per-class recall.
    raise NotImplementedError


def main():
    # TODO: build manifest, fixed split, no-augmentation dataloaders, model skeleton.
    # Do not train in this benchmark.
    raise NotImplementedError


if __name__ == "__main__":
    main()
'''
    return plan, skeleton


def _rag_plan_and_skeleton(summary: str) -> tuple[str, str]:
    plan = f"""# Baseline Plan - WikiQA BM25 Retrieval

Dataset summary: {summary}

1. Treat each question's candidate answer sentences as the retrieval pool.
2. Keep the provided train/dev/test TSV files as fixed splits.
3. Build a BM25 lexical baseline before dense retrieval or generation.
4. Evaluate retrieval only: Recall@k, MRR, and source-hit rate over labeled positives.
5. Do not evaluate generation until retrieval reaches the target Recall@k.
6. Stop after writing the script skeleton; do not run retrieval in this benchmark.
"""
    skeleton = '''"""BM25 retrieval baseline skeleton for WikiQA.

This file is intentionally not executed by the benchmark.
"""

from pathlib import Path

DATA_DIR = Path("tests/datasets/wikiqa")
SPLITS = {
    "train": DATA_DIR / "WikiQA-train.tsv",
    "dev": DATA_DIR / "WikiQA-dev.tsv",
    "test": DATA_DIR / "WikiQA-test.tsv",
}
K_VALUES = (1, 3, 5, 10)


def load_split(path):
    # TODO: read TSV with QuestionID, Question, SentenceID, Sentence, Label.
    raise NotImplementedError


def build_bm25_index(candidate_sentences):
    # TODO: tokenize sentences and initialize a BM25 retriever.
    raise NotImplementedError


def rank_candidates(question, retriever, candidate_ids):
    # TODO: rank candidates for one question.
    raise NotImplementedError


def evaluate_rankings(rankings, labels):
    # TODO: Recall@k, MRR, and source-hit rate.
    raise NotImplementedError


def main():
    # TODO: load fixed splits and define BM25 retrieval-eval flow.
    # Do not run retrieval in this benchmark.
    raise NotImplementedError


if __name__ == "__main__":
    main()
'''
    return plan, skeleton


def build_scenarios() -> list[Scenario]:
    data_root = ROOT / "tests" / "datasets"

    ml_summary = _vsmec_summary(data_root / "vsmec")
    ml_plan, ml_skeleton = _ml_plan_and_skeleton(ml_summary)

    dl_summary = _alpaca_summary(data_root / "alpaca-dataset" / "dataset")
    dl_plan, dl_skeleton = _dl_plan_and_skeleton(dl_summary)

    rag_summary = _wikiqa_summary(data_root / "wikiqa")
    rag_plan, rag_skeleton = _rag_plan_and_skeleton(rag_summary)

    return [
        Scenario(
            key="ML",
            title="Vietnamese emotion classifier",
            prompt=(
                "You are an ML engineer. Build a Vietnamese text emotion classifier using "
                "`tests/datasets/vsmec` on CPU. Start with a simple reproducible baseline "
                "(TF-IDF + Logistic Regression) BEFORE any transformer; use the provided "
                "train/valid/test split and report macro-F1 and per-class recall, not "
                "accuracy. Change exactly one thing per experiment, check for duplicate/leaked "
                "samples across splits, and never tune on the test set. Produce the baseline "
                "plan and a baseline training-script skeleton, then STOP (do not run it)."
            ),
            state=ProjectState(
                project_name="VSMEC Emotion Classifier",
                project_goal="Build a Vietnamese social-media emotion classifier from VSMEC.",
                target_users="ML engineers",
                project_type="machine learning",
                task_type="text_classification",
                input_type="text",
                output_type="emotion_label",
                dataset_status="available",
                dataset_size_note=ml_summary,
                has_labels=True,
                has_class_imbalance=True,
                main_metric="macro_f1",
                baseline_model="TF-IDF + Logistic Regression",
                runtime=["claude", "codex"],
                compute=ComputeConfig(has_gpu=False, environment=None, budget_note="CPU only"),
            ),
            dataset_summary=ml_summary,
            plan=ml_plan,
            skeleton=ml_skeleton,
        ),
        Scenario(
            key="DL",
            title="Alpaca image classifier",
            prompt=(
                "You are a DL engineer on CPU. Build an image classifier using "
                "`tests/datasets/alpaca-dataset/dataset`, a small imbalanced dataset. Start "
                "with a transfer-learning baseline (fine-tune a pretrained ResNet/MobileNet) "
                "with NO augmentation first; use a stratified split, define a quick smoke "
                "test, and report macro-F1 and per-class recall. Add augmentation only after "
                "the baseline, watch for overfitting and train/val leakage, and never tune on "
                "the test set. Produce the baseline plan and a baseline training-script "
                "skeleton, then STOP (do not run it)."
            ),
            state=ProjectState(
                project_name="Alpaca Image Classifier",
                project_goal="Build a small Alpaca vs not-alpaca image classifier.",
                target_users="DL engineers",
                project_type="deep learning",
                task_type="image_classification",
                input_type="image",
                output_type="class_label",
                dataset_status="available",
                dataset_size_note=dl_summary,
                has_labels=True,
                has_class_imbalance=True,
                main_metric="macro_f1",
                baseline_model="Pretrained ResNet",
                runtime=["claude", "codex"],
                compute=ComputeConfig(has_gpu=False, environment=None, budget_note="CPU benchmark"),
            ),
            dataset_summary=dl_summary,
            plan=dl_plan,
            skeleton=dl_skeleton,
        ),
        Scenario(
            key="RAG",
            title="WikiQA BM25 retrieval",
            prompt=(
                "You are a RAG engineer. Build a retrieval-augmented QA retrieval baseline "
                "using `tests/datasets/wikiqa`. Establish retrieval quality FIRST: use the "
                "fixed WikiQA train/dev/test files and a BM25 baseline before dense retrieval, "
                "and report Recall@k / MRR / source-hit rate. Tune chunking and retrieval "
                "before any generation/prompt changes, require every answer to cite a "
                "retrieved source chunk, and do not evaluate generation until retrieval hits "
                "the target Recall@k. Produce the retrieval-eval plan and a BM25 baseline "
                "script skeleton, then STOP (do not run it)."
            ),
            state=ProjectState(
                project_name="WikiQA Retrieval Baseline",
                project_goal="Build retrieval evaluation over WikiQA before any generation.",
                target_users="RAG engineers",
                project_type="rag",
                task_type="rag",
                input_type="documents",
                output_type="cited_answer",
                dataset_status="available",
                dataset_size_note=rag_summary,
                has_labels=True,
                has_class_imbalance=None,
                main_metric="Recall@k",
                baseline_model="BM25",
                runtime=["claude", "codex"],
                compute=ComputeConfig(has_gpu=False, environment=None, budget_note="CPU BM25"),
            ),
            dataset_summary=rag_summary,
            plan=rag_plan,
            skeleton=rag_skeleton,
        ),
    ]


def _render_octopus_project(project_dir: Path, scenario: Scenario) -> tuple[int, int]:
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

        manual_docs_tokens = sum(
            estimate_tokens(Path(doc).read_text(encoding="utf-8"))
            for doc in PLANNING_DOCS
            if Path(doc).exists()
        )
        octopus_context_tokens = estimate_tokens(
            Path(".octopus/context/current_context.md").read_text(encoding="utf-8")
        )
        return manual_docs_tokens, octopus_context_tokens
    finally:
        os.chdir(original)


def run_benchmark() -> list[BenchmarkRow]:
    scenarios = build_scenarios()
    root = Path(tempfile.mkdtemp(prefix="octopus-dataset-token-bench-"))
    rows: list[BenchmarkRow] = []

    for scenario in scenarios:
        project_dir = root / scenario.key.lower()
        project_dir.mkdir(parents=True)
        output_dir = project_dir / "baseline_deliverable"
        output_dir.mkdir()

        (output_dir / "baseline_plan.md").write_text(scenario.plan, encoding="utf-8")
        (output_dir / "baseline_script_skeleton.py").write_text(scenario.skeleton, encoding="utf-8")

        manual_docs_tokens, octopus_context_tokens = _render_octopus_project(project_dir, scenario)
        a_input = estimate_tokens(scenario.prompt) + estimate_tokens(scenario.dataset_summary)
        a_input += manual_docs_tokens
        b_input = estimate_tokens(OCTOPUS_PROMPT) + octopus_context_tokens
        deliverable = estimate_tokens(scenario.plan) + estimate_tokens(scenario.skeleton)

        rows.append(
            BenchmarkRow(
                scenario=scenario.key,
                a_input_tokens=a_input,
                b_input_tokens=b_input,
                saving_pct=round((a_input - b_input) / a_input * 100, 1),
                deliverable_tokens=deliverable,
                output_dir=output_dir,
            )
        )

    return rows


def format_markdown(rows: list[BenchmarkRow]) -> str:
    lines = [
        f"Tokenizer: `{ENCODING}`",
        "",
        "| Scenario | A prompt-only input | B Octopus input | Saving % | Plan+script output |",
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
    rows = run_benchmark()
    print(format_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
