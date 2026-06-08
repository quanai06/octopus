from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from octopus.core.files import atomic_write_text
from octopus.core.paths import FAILURES_MD, NEXT_STEPS_MD, NEXT_STEPS_YAML
from octopus.core.schemas import NextDirection
from octopus.experiments.analyze import (
    LOW_RECALL_THRESHOLD,
    detect_imbalance,
    detect_metric_gap,
    detect_overfitting,
    detect_underfitting,
    detect_unstable_training,
)
from octopus.experiments.technique_library import (
    DOMAIN_RAG,
    SYMPTOM_CLASS_IMBALANCE,
    SYMPTOM_LARGE_GAP,
    SYMPTOM_LOW_RETRIEVAL,
    SYMPTOM_METRIC_GAP,
    SYMPTOM_NEAR_TARGET,
    SYMPTOM_OVERFITTING,
    SYMPTOM_UNDERFITTING,
    SYMPTOM_UNSTABLE,
    Technique,
    antipatterns_for,
    domain_for,
    techniques_for,
)
from octopus.storage.experiment_store import list_experiments, load_experiment_index
from octopus.storage.state_store import load_state, state_exists

SMALL_GAP = 0.03
MODERATE_GAP = 0.10


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
        task_type = state.task_type if state else None
        directions = _directions_from_signals(
            best, completed, target_gap, project_type, task_type
        )

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
            *_bullet_list(_unlikely(directions, best, completed, state)),
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


@dataclass(frozen=True)
class _DirectionTemplate:
    symptoms: tuple[str, ...]
    title: str
    priority: int
    expected_impact: str
    rationale: str
    files_to_read: tuple[str, ...]
    files_to_edit: tuple[str, ...]
    confidence: str = "high"
    risk: str = "low"
    cost: str = "low"
    stop_condition: str = "Run one controlled change and compare against the current best run."
    force_optional: bool = False


# Symptom-level direction frames, in priority order. The concrete techniques,
# guardrails, and cost/risk come from the technique library so the ML knowledge
# lives in one place.
_DIRECTION_TEMPLATES: tuple[_DirectionTemplate, ...] = (
    _DirectionTemplate(
        symptoms=(SYMPTOM_LOW_RETRIEVAL,),
        title="Improve retrieval recall before changing the generator",
        priority=1,
        expected_impact="Raise Recall@k / source-hit so generation can be trusted.",
        rationale=(
            "RAG quality must be improved from measured retrieval before prompt or "
            "generation changes."
        ),
        files_to_read=("retriever", "embedding", "chunk", "index", "eval"),
        files_to_edit=("retriever", "eval", "metrics"),
        confidence="medium",
        cost="medium",
        stop_condition="Retrieval eval reports Recall@k / source-hit for a fixed query set.",
    ),
    _DirectionTemplate(
        symptoms=(SYMPTOM_CLASS_IMBALANCE, SYMPTOM_METRIC_GAP),
        title="Improve minority recall with class weighting",
        priority=1,
        expected_impact=(
            "Improve macro F1 and minority recall without a large architecture change."
        ),
        rationale=(
            "The strongest evidence points to uneven per-class performance, so fix the "
            "objective/sampling before changing the backbone."
        ),
        files_to_read=("loss", "class_weight", "sampler", "dataset", "label", "metrics"),
        files_to_edit=("training config", "loss function", "dataset sampler", "metrics"),
        stop_condition=(
            "New run improves macro_f1 or minority recall without lowering overall "
            "validation quality."
        ),
    ),
    _DirectionTemplate(
        symptoms=(SYMPTOM_OVERFITTING,),
        title="Reduce overfitting with early stopping and regularization",
        priority=2,
        expected_impact="Stabilize validation score and reduce wasted epochs.",
        rationale=(
            "Training and validation evidence suggests the model is fitting training data "
            "faster than validation quality improves."
        ),
        files_to_read=("trainer", "early_stopping", "dropout", "weight_decay", "config"),
        files_to_edit=("training config", "trainer callbacks"),
        stop_condition=(
            "Validation loss no longer diverges while the main metric stays stable or improves."
        ),
    ),
    _DirectionTemplate(
        symptoms=(SYMPTOM_UNSTABLE,),
        title="Stabilize optimization",
        priority=3,
        expected_impact="Reduce noisy validation behavior.",
        rationale="Loss instability should be handled before interpreting model quality.",
        files_to_read=("optimizer", "scheduler", "lr", "warmup", "batch", "fp16"),
        files_to_edit=("optimizer config", "training config"),
        confidence="medium",
        stop_condition="Loss curves stop spiking or diverging on a repeatable run.",
    ),
    _DirectionTemplate(
        symptoms=(SYMPTOM_UNDERFITTING,),
        title="Check preprocessing and capacity for underfitting",
        priority=4,
        expected_impact="Find pipeline issues or justify a stronger model.",
        rationale=(
            "Both train and validation signals are weak, so first verify the input pipeline "
            "and basic capacity."
        ),
        files_to_read=("preprocess", "dataset", "model", "train", "metrics"),
        files_to_edit=("preprocessing", "model config"),
        confidence="medium",
        risk="medium",
        cost="medium",
        stop_condition="One-batch sanity check passes or a preprocessing defect is fixed.",
    ),
    _DirectionTemplate(
        symptoms=(SYMPTOM_NEAR_TARGET,),
        title="Run a low-risk metric-focused refinement",
        priority=5,
        expected_impact="Close a small gap without destabilizing the training setup.",
        rationale=(
            "The target gap is small, so avoid broad rewrites and prefer one small measured "
            "change."
        ),
        files_to_read=("metrics", "threshold", "evaluate", "config"),
        files_to_edit=("evaluation config", "training config"),
        confidence="medium",
        stop_condition="Main metric crosses the target or stops improving after one change.",
        force_optional=True,
    ),
)


def _directions_from_signals(
    best, completed, target_gap: float | None, project_type: str, task_type: str | None
) -> list[NextDirection]:
    domain = domain_for(task_type, project_type)
    signals = {
        signal.name: signal
        for signal in _detect_signals(best, completed)
        if signal.status == "detected"
    }
    symptoms = _symptom_set(set(signals), domain, best, target_gap)

    directions: list[NextDirection] = []
    next_id = 1
    for template in _DIRECTION_TEMPLATES:
        matched = [name for name in template.symptoms if name in symptoms]
        if not matched:
            continue
        techniques = techniques_for(domain, list(template.symptoms))
        if not techniques:
            continue
        evidence = _template_evidence(matched, signals, target_gap)
        directions.append(
            _build_direction(next_id, template, techniques, evidence, already_used=bool(directions))
        )
        next_id += 1

    return directions or [_generic_next_direction(best.id)]


def _detect_signals(best, completed):
    history = list(completed)
    return [
        detect_imbalance(best, history),
        detect_metric_gap(best, history),
        detect_overfitting(best, history),
        detect_unstable_training(best, history),
        detect_underfitting(best, history),
    ]


def _symptom_set(detected: set[str], domain: str, best, target_gap: float | None) -> set[str]:
    symptoms = set(detected)
    if domain == DOMAIN_RAG and _looks_like_low_retrieval(best, target_gap):
        symptoms.add(SYMPTOM_LOW_RETRIEVAL)
    if target_gap is not None:
        if 0 < target_gap <= SMALL_GAP:
            symptoms.add(SYMPTOM_NEAR_TARGET)
        elif target_gap > MODERATE_GAP:
            symptoms.add(SYMPTOM_LARGE_GAP)
    return symptoms


def _looks_like_low_retrieval(best, target_gap: float | None) -> bool:
    retrieval_values = [
        value
        for key, value in best.metrics.items()
        if any(token in key.lower() for token in ("recall", "hit", "mrr", "ndcg"))
    ]
    if retrieval_values and min(retrieval_values) < LOW_RECALL_THRESHOLD:
        return True
    return target_gap is not None and target_gap > MODERATE_GAP


def _template_evidence(matched, signals, target_gap: float | None) -> list[str]:
    evidence: list[str] = []
    for name in matched:
        signal = signals.get(name)
        if signal:
            evidence.extend(signal.evidence)
    if not evidence and target_gap is not None:
        evidence.append(f"target_gap={target_gap:+.3f}")
    return evidence or ["See the training review for diagnosis evidence."]


def _build_direction(
    next_id: int,
    template: _DirectionTemplate,
    techniques: list[Technique],
    evidence: list[str],
    *,
    already_used: bool,
) -> NextDirection:
    names = ", ".join(technique.name for technique in techniques[:4])
    guardrails = _dedup(
        [guardrail for technique in techniques[:3] for guardrail in technique.guardrails]
    )[:4]
    guardrails.append(
        "Do not change train/validation/test split unless this is the selected direction."
    )
    recommendation = "optional" if (already_used or template.force_optional) else "recommended"
    return NextDirection(
        direction_id=f"D{next_id}",
        title=template.title,
        priority=template.priority,
        recommendation=recommendation,  # type: ignore[arg-type]
        rationale=f"{template.rationale} Suggested techniques in priority order: {names}.",
        evidence=evidence,
        confidence=template.confidence,  # type: ignore[arg-type]
        risk=template.risk,  # type: ignore[arg-type]
        cost=template.cost,  # type: ignore[arg-type]
        expected_impact=template.expected_impact,
        files_to_read=list(template.files_to_read),
        files_to_edit=list(template.files_to_edit),
        commands_to_run=["pytest -q"],
        guardrails=_dedup(guardrails),
        stop_condition=template.stop_condition,
    )


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


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


def _unlikely(directions: list[NextDirection], best, completed, state) -> list[str]:
    if any(direction.recommendation == "blocked" for direction in directions):
        return ["Main-model work should wait until baseline evidence exists."]
    if best is None:
        return ["No unsupported avoid rule detected."]
    domain = domain_for(
        state.task_type if state else None,
        state.project_type if state else None,
    )
    target_gap = None
    if state and state.target_score is not None:
        main_metric = _main_metric([best, *completed])
        if main_metric in best.metrics:
            target_gap = state.target_score - best.metrics[main_metric]
    detected = {
        signal.name
        for signal in _detect_signals(best, completed)
        if signal.status == "detected"
    }
    symptoms = _symptom_set(detected, domain, best, target_gap)
    antis = antipatterns_for(list(symptoms))
    if not antis:
        return ["No unsupported avoid rule detected."]
    return [f"{anti.name} — {anti.reason}" for anti in antis]


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None."]


def _path_bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items] if items else ["- None."]
