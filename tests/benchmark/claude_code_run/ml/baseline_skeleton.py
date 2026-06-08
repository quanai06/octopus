"""TF-IDF + Logistic Regression baseline for Vietnamese emotion classification.

Claude Code baseline deliverable (eval). Encodes the decisions from
.octopus/context/current_context.md. Not executed by the benchmark.
"""

from __future__ import annotations

from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score

DATA_DIR = Path("data/vsmec")  # frozen splits; do NOT re-split here
SEED = 42
TEXT_COL, LABEL_COL = "Sentence", "Emotion"


def load_split(name: str):
    """Load a frozen split (train/valid/test). Test stays untouched until final."""
    # TODO: read DATA_DIR / f"{name}.xlsx" -> (texts, labels)
    raise NotImplementedError


def assert_no_leakage(train_texts, valid_texts, test_texts) -> None:
    """Fail if the same normalized text appears across splits (duplicate leakage)."""
    norm = lambda xs: {t.strip().lower() for t in xs}  # noqa: E731
    train = norm(train_texts)
    if train & norm(valid_texts) or train & norm(test_texts):
        raise ValueError("Duplicate text leaks across splits — fix the split first.")


def build_baseline() -> tuple[TfidfVectorizer, LogisticRegression]:
    # class_weight="balanced" is the single controlled change for imbalance.
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=SEED)
    return vectorizer, clf


def main() -> None:
    x_train, y_train = load_split("train")
    x_valid, y_valid = load_split("valid")
    x_test, _ = load_split("test")  # loaded for the leakage check only
    assert_no_leakage(x_train, x_valid, x_test)

    vectorizer, clf = build_baseline()
    clf.fit(vectorizer.fit_transform(x_train), y_train)  # fit on TRAIN only

    pred = clf.predict(vectorizer.transform(x_valid))  # evaluate on VALIDATION
    print("macro_f1:", f1_score(y_valid, pred, average="macro"))
    print(classification_report(y_valid, pred, digits=3))  # per-class recall
    print(confusion_matrix(y_valid, pred))
    # NOTE: the test set is intentionally never used for tuning/selection here.


if __name__ == "__main__":
    main()
