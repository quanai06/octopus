"""MobileNet transfer-learning baseline (no augmentation) for image classification.

Claude Code baseline deliverable (eval). Encodes the decisions from
.octopus/context/current_context.md. Not executed by the benchmark.
"""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data/alpaca")  # frozen stratified split; do NOT re-split
SEED = 42
SMOKE_TEST_BATCHES = 2  # tiny run first to catch pipeline bugs


def build_dataloaders(split: str, augment: bool = False):
    """Frozen split loader. Baseline runs with augment=False on purpose."""
    # TODO: ImageFolder(DATA_DIR / split); no augmentation in the baseline.
    raise NotImplementedError


def build_model(num_classes: int):
    """Pretrained MobileNetV2 with a frozen backbone + fresh classifier head."""
    import torchvision  # local import keeps the skeleton importable without torch

    model = torchvision.models.mobilenet_v2(weights="DEFAULT")
    for param in model.features.parameters():
        param.requires_grad = False  # freeze backbone for the baseline
    model.classifier[1] = torchvision.nn.Linear(model.last_channel, num_classes)
    return model


def evaluate(model, loader) -> dict:
    """Return macro_f1 + per-class recall on the given (validation) loader."""
    # TODO: collect preds/labels; sklearn f1_score(average="macro") + per-class recall.
    raise NotImplementedError


def main() -> None:
    train_loader = build_dataloaders("train", augment=False)  # no aug in baseline
    valid_loader = build_dataloaders("valid")
    model = build_model(num_classes=2)

    # 1) smoke test on a few batches before committing to full training
    _smoke(model, train_loader, max_batches=SMOKE_TEST_BATCHES)
    # 2) train head only; monitor val macro_f1 + train/val gap (overfitting)
    # 3) evaluate on validation only; the test set stays untouched until final
    print(evaluate(model, valid_loader))


def _smoke(model, loader, max_batches: int) -> None:
    # TODO: run max_batches forward/backward steps; assert loss is finite.
    raise NotImplementedError


if __name__ == "__main__":
    main()
