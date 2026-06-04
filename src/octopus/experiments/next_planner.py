from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import FAILURES_MD, NEXT_STEPS_MD, NEXT_STEPS_YAML
from octopus.core.schemas import NextDirection
from octopus.experiments.analyze import (
    detect_imbalance,
    detect_metric_gap,
    detect_overfitting,
    detect_underfitting,
    detect_unstable_training,
)
from octopus.storage.experiment_store import list_experiments, load_experiment_index
from octopus.storage.state_store import load_state, state_exists


def generate_next_directions(top_k: int | None = None) -> list[NextDirection]:
    records = list_experiments()
    completed = [record for record in records if record.status == "completed"]
    main_metric = _main_metric(records)
    baseline = _best_baseline(completed, main_metric)
    best = _best_by_metric(completed, main_metric)
    state = load_state() if state_exists() else None

    if baseline is None:
        directions = _baseline_first_directions(state is not None and state.project_type == "rag")
    else:
        target_gap = None
        if state and state.target_score is not None and best and main_metric in best.metrics:
            target_gap = state.target_score - best.metrics[main_metric]
        project_type = state.project_type if state else ""
        directions = _directions_from_signals(best, completed, target_gap, project_type)

    directions = _filter_failed_directions(directions)
    ranked = rank_directions(directions)
    if top_k is not None:
        return ranked[:top_k]
    return ranked


def rank_directions(directions: list[NextDirection]) -> list[NextDirection]:
    return sorted(directions, key=lambda direction: (direction.priority, direction.direction_id))


def write_next_steps_markdown(
    directions: list[NextDirection], output: Path | None = None
) -> Path:
    output_path = output or NEXT_STEPS_MD
    records = list_experiments()
    completed = [record for record in records if record.status == "completed"]
    main_metric = _main_metric(records)
    best = _best_by_metric(completed, main_metric)
    state = load_state() if state_exists() else None
    recommended = next((item for item in directions if item.recommendation == "recommended"), None)
    lines = [
        f"# Next Steps - {(state.project_name if state else None) or 'Unnamed Project'}",
        "",
        f"> Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"> Based on: {len(records)} experiments",
        f"> Current best: {(best.id if best else 'not available')}",
        f"> Main metric: {main_metric}",
        f"> Target: {_target_text(state)}",
        "",
        "---",
        "",
        "## 1. Current Result",
        "",
        "| Experiment | Kind | Model | Main Metric | Status |",
        "|---|---|---|---:|---|",
    ]
    for record in records:
        lines.append(
            f"| {record.id} | {record.kind} | {record.model or '-'} | "
            f"{_metric_value(record, main_metric)} | {record.status} |"
        )
    if not records:
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## 2. Diagnosis Summary",
            "",
            f"### Main bottleneck\n{_main_bottleneck(directions)}",
            "",
            "### Evidence",
            *_bullet_list(_all_evidence(directions)),
            "",
            "### What is unlikely",
            *_bullet_list(_unlikely(directions)),
            "",
            "## 3. Ranked Directions",
            "",
        ]
    )
    for direction in directions:
        lines.extend(
            [
                f"### {direction.direction_id} - {direction.title}",
                "",
                f"**Recommendation:** {direction.recommendation}",
                f"**Confidence:** {direction.confidence}",
                f"**Risk:** {direction.risk}",
                f"**Cost:** {direction.cost}",
                f"**Expected impact:** {direction.expected_impact or 'not specified'}",
                "",
                "**Why this direction:**",
                direction.rationale,
                "",
                "**Evidence:**",
                *_bullet_list(direction.evidence),
                "",
                "**Files to read:**",
                *_path_bullets(direction.files_to_read),
                "",
                "**Likely files to edit:**",
                *_path_bullets(direction.files_to_edit),
                "",
                "**Commands to run:**",
                "```bash",
                *direction.commands_to_run,
                "```",
                "",
                "**Guardrails:**",
                *_bullet_list(direction.guardrails),
                "",
                "**Stop condition:**",
                direction.stop_condition or "Stop after one controlled experiment.",
                "",
                "---",
                "",
            ]
        )
    lines.extend(
        [
            "## 4. Recommended Choice",
            "",
            f"Choose {(recommended.direction_id if recommended else 'D1')} first.",
            "",
            f"Reason: {(recommended.rationale if recommended else 'highest ranked direction')}",
            "",
            "## 5. Build Agent Context",
            "",
            "```bash",
            f"octopus exp choose {(recommended.direction_id if recommended else 'D1')}",
            (
                "octopus context --direction "
                f"{(recommended.direction_id if recommended else 'D1')} --target codex"
            ),
            "```",
            "",
            "## 6. Global Guardrails",
            "",
            (
                "- Do not change train/validation/test split unless the selected direction "
                "explicitly says so."
            ),
            "- Do not tune on the test set.",
            "- Do not implement multiple directions at once.",
            "- Log the next run with `octopus exp ingest`.",
            "",
        ]
    )
    atomic_write_text(output_path, "\n".join(lines))
    return output_path


def write_next_steps_yaml(directions: list[NextDirection]) -> Path:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "octopus exp next",
        "directions": [direction.model_dump(mode="json") for direction in directions],
    }
    atomic_write_text(NEXT_STEPS_YAML, yaml.safe_dump(payload, sort_keys=False))
    return NEXT_STEPS_YAML


def _directions_from_signals(
    best, completed, target_gap: float | None, project_type: str
) -> list[NextDirection]:
    history = list(completed)
    signals = [
        detect_imbalance(best, history),
        detect_metric_gap(best, history),
        detect_overfitting(best, history),
        detect_unstable_training(best, history),
        detect_underfitting(best, history),
    ]
    detected = {signal.name: signal for signal in signals if signal.status == "detected"}
    directions: list[NextDirection] = []
    next_id = 1

    if project_type == "rag":
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Build retrieval evaluation before prompt changes",
                priority=1,
                recommendation="recommended",
                rationale=(
                    "RAG quality should be improved from measured retrieval recall and "
                    "citation coverage before prompt-only changes."
                ),
                evidence=["project_type=rag"],
                confidence="medium",
                risk="low",
                cost="medium",
                expected_impact=(
                    "Expose retrieval bottlenecks and prevent unsupported answer tuning."
                ),
                files_to_read=["retriever", "embedding", "chunk", "index", "prompt"],
                files_to_edit=["retriever", "eval", "metrics"],
                commands_to_run=["pytest -q"],
                guardrails=[
                    "Require citation and faithfulness checks.",
                    "Do not tune on private eval answers.",
                ],
                stop_condition=(
                    "Retrieval eval reports recall/source-hit metrics for a fixed query set."
                ),
            )
        )
        next_id += 1

    if "class_imbalance" in detected or "metric_gap" in detected:
        evidence = detected.get("class_imbalance", detected.get("metric_gap")).evidence
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Improve minority recall with class weighting",
                priority=1,
                recommendation="recommended",
                rationale=(
                    "The strongest evidence points to uneven per-class performance, so fix "
                    "the objective/sampling before changing the backbone."
                ),
                evidence=evidence,
                confidence="high",
                risk="low",
                cost="low",
                expected_impact=(
                    "Improve macro F1 and minority recall without a large architecture change."
                ),
                files_to_read=["loss", "class_weight", "sampler", "dataset", "label", "metrics"],
                files_to_edit=["training config", "loss function", "dataset sampler", "metrics"],
                commands_to_run=["pytest -q"],
                guardrails=[
                    "Do not change train/validation/test split.",
                    "Track macro_f1 and per-class recall.",
                    "Change only weighting/sampling in the next run.",
                ],
                stop_condition=(
                    "New run improves macro_f1 or minority recall without lowering overall "
                    "validation quality."
                ),
            )
        )
        next_id += 1

    if "overfitting" in detected:
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Reduce overfitting with early stopping and regularization",
                priority=2,
                recommendation="recommended" if not directions else "optional",
                rationale=(
                    "Training and validation evidence suggests the model is fitting training "
                    "data faster than validation quality improves."
                ),
                evidence=detected["overfitting"].evidence,
                confidence="high",
                risk="low",
                cost="low",
                expected_impact="Stabilize validation score and reduce wasted epochs.",
                files_to_read=["trainer", "early_stopping", "dropout", "weight_decay", "config"],
                files_to_edit=["training config", "trainer callbacks"],
                commands_to_run=["pytest -q"],
                guardrails=[
                    "Do not increase epochs as the first response.",
                    "Keep the same validation split.",
                ],
                stop_condition=(
                    "Validation loss no longer diverges while main metric stays stable or "
                    "improves."
                ),
            )
        )
        next_id += 1

    if "unstable_training" in detected:
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Stabilize optimization",
                priority=3,
                recommendation="recommended" if not directions else "optional",
                rationale="Loss instability should be handled before interpreting model quality.",
                evidence=detected["unstable_training"].evidence,
                confidence="medium",
                risk="low",
                cost="low",
                expected_impact="Reduce noisy validation behavior.",
                files_to_read=["optimizer", "scheduler", "lr", "warmup", "batch", "fp16"],
                files_to_edit=["optimizer config", "training config"],
                commands_to_run=["pytest -q"],
                guardrails=[
                    "Lower learning rate before increasing model complexity.",
                    "Check NaN/inf handling.",
                ],
                stop_condition="Loss curves stop spiking or diverging on a repeatable run.",
            )
        )
        next_id += 1

    if "underfitting" in detected:
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Check preprocessing and capacity for underfitting",
                priority=4,
                recommendation="recommended" if not directions else "optional",
                rationale=(
                    "Both train and validation signals are weak, so first verify input "
                    "pipeline and basic capacity."
                ),
                evidence=detected["underfitting"].evidence,
                confidence="medium",
                risk="medium",
                cost="medium",
                expected_impact="Find pipeline issues or justify a stronger model.",
                files_to_read=["preprocess", "dataset", "model", "train", "metrics"],
                files_to_edit=["preprocessing", "model config"],
                commands_to_run=["pytest -q"],
                guardrails=["Run a one-batch overfit sanity check before large sweeps."],
                stop_condition="One-batch sanity check passes or preprocessing defect is fixed.",
            )
        )
        next_id += 1

    if target_gap is not None and 0 < target_gap <= 0.03:
        directions.append(
            NextDirection(
                direction_id=f"D{next_id}",
                title="Run a low-risk metric-focused refinement",
                priority=5,
                recommendation="optional",
                rationale=(
                    "The target gap is small, so avoid broad rewrites and prefer one small "
                    "measured change."
                ),
                evidence=[f"target_gap={target_gap:+.3f}"],
                confidence="medium",
                risk="low",
                cost="low",
                expected_impact="Close a small gap without destabilizing the training setup.",
                files_to_read=["metrics", "threshold", "evaluate", "config"],
                files_to_edit=["evaluation config", "training config"],
                commands_to_run=["pytest -q"],
                guardrails=[
                    "Do not tune on the test set.",
                    "Keep the comparison metric unchanged.",
                ],
                stop_condition=(
                    "Main metric crosses target or no longer improves after one controlled "
                    "change."
                ),
            )
        )

    return directions or [_generic_next_direction(best.id)]


def _baseline_first_directions(is_rag: bool) -> list[NextDirection]:
    read_files = ["experiment_plan.md", "data_strategy.md", "metrics", "baseline"]
    if is_rag:
        read_files.extend(["retriever", "eval", "chunk"])
    return [
        NextDirection(
            direction_id="D1",
            title="Create a reproducible baseline first",
            priority=1,
            recommendation="recommended",
            rationale=(
                "No completed baseline exists, so main-model work should wait until there "
                "is a stable comparison point."
            ),
            evidence=["no completed baseline experiment found"],
            confidence="high",
            risk="low",
            cost="low",
            expected_impact="Establish the minimum comparison run for future controlled changes.",
            files_to_read=read_files,
            files_to_edit=["baseline training script", "metrics logging"],
            commands_to_run=["pytest -q"],
            guardrails=["Do not start a main-model direction before logging the baseline."],
            stop_condition="A completed baseline is ingested with the project main metric.",
        ),
        NextDirection(
            direction_id="D2",
            title="Main model training",
            priority=99,
            recommendation="blocked",
            rationale="Main-model work is blocked until a completed baseline has been logged.",
            evidence=["baseline_required=true"],
            confidence="high",
            risk="high",
            cost="high",
            expected_impact="Blocked direction.",
            files_to_read=[],
            files_to_edit=[],
            commands_to_run=[],
            guardrails=["Log a baseline first."],
            stop_condition="Baseline exists.",
        ),
    ]


def _generic_next_direction(best_id: str) -> NextDirection:
    return NextDirection(
        direction_id="D1",
        title="Run focused error analysis",
        priority=10,
        recommendation="recommended",
        rationale=(
            "No strong deterministic failure signal was detected, so inspect errors before "
            "adding complexity."
        ),
        evidence=[f"current_best={best_id}"],
        confidence="medium",
        risk="low",
        cost="low",
        expected_impact="Identify the next controlled experiment from real mistakes.",
        files_to_read=["metrics", "classification_report", "confusion", "dataset"],
        files_to_edit=["evaluation report"],
        commands_to_run=["pytest -q"],
        guardrails=["Do not implement multiple changes at once."],
        stop_condition="Error analysis identifies one measurable bottleneck.",
    )


def _filter_failed_directions(directions: list[NextDirection]) -> list[NextDirection]:
    if not FAILURES_MD.exists():
        return directions
    failures = FAILURES_MD.read_text(encoding="utf-8").lower()
    filtered: list[NextDirection] = []
    for direction in directions:
        title = direction.title.lower()
        if "increase epochs" in failures and "epoch" in title:
            continue
        filtered.append(direction)
    return filtered or directions


def _main_metric(records) -> str:
    index = load_experiment_index()
    if index.get("main_metric"):
        return str(index["main_metric"])
    if state_exists():
        state = load_state()
        if state.main_metric:
            return state.main_metric
    for preferred in ("macro_f1", "accuracy", "f1", "rmse", "mae"):
        if any(preferred in record.metrics for record in records):
            return preferred
    return "macro_f1"


def _best_baseline(records, metric: str):
    return _best_by_metric([record for record in records if record.kind == "baseline"], metric)


def _best_by_metric(records, metric: str):
    candidates = [record for record in records if metric in record.metrics]
    return max(candidates, key=lambda record: record.metrics[metric]) if candidates else None


def _target_text(state) -> str:
    return "not set" if state is None or state.target_score is None else f"{state.target_score:g}"


def _metric_value(record, metric: str) -> str:
    value = record.metrics.get(metric)
    return "not available" if value is None else f"{value:g}"


def _main_bottleneck(directions: list[NextDirection]) -> str:
    recommended = next((item for item in directions if item.recommendation == "recommended"), None)
    return recommended.title if recommended else "No recommended direction."


def _all_evidence(directions: list[NextDirection]) -> list[str]:
    evidence: list[str] = []
    for direction in directions:
        evidence.extend(direction.evidence)
    return evidence[:8]


def _unlikely(directions: list[NextDirection]) -> list[str]:
    if any("minority" in direction.title.lower() for direction in directions):
        return ["A larger backbone is unlikely to be the safest first fix."]
    if any("overfitting" in direction.title.lower() for direction in directions):
        return ["More epochs are unlikely to help before regularization."]
    if any(direction.recommendation == "blocked" for direction in directions):
        return ["Main-model work should wait until baseline evidence exists."]
    return ["No unsupported avoid rule detected."]


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None."]


def _path_bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items] if items else ["- None."]
