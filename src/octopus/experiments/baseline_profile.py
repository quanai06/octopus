"""Baseline understanding.

Before tuning, Octopus characterizes the baseline run: where it stands vs the
target, whether it is bias- or variance-limited, which classes are weak, what
data-quality risks are implied, and — drawing on the technique library — which
concrete techniques are justified next (and which to avoid for now).

Deterministic and offline. Reuses the detectors in ``analyze.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from octopus.core.files import atomic_write_text
from octopus.core.paths import BASELINE_PROFILE_MD
from octopus.core.schemas import (
    BaselineProfile,
    DiagnosisSignal,
    ExperimentRecord,
    TechniqueSuggestion,
    WeakClass,
)
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
    SYMPTOM_HEALTHY,
    SYMPTOM_LARGE_GAP,
    SYMPTOM_LOW_RETRIEVAL,
    SYMPTOM_NEAR_TARGET,
    antipatterns_for,
    domain_for,
    techniques_for,
)
from octopus.storage.experiment_store import list_experiments, load_experiment
from octopus.storage.state_store import load_state, state_exists

# Headroom bands on the target gap (positive gap = below target).
SMALL_GAP = 0.03
MODERATE_GAP = 0.10


class NoBaselineError(RuntimeError):
    """Raised when no completed baseline experiment is available to profile."""


def profile_baseline(experiment_id: str | None = None, top_k: int = 5) -> BaselineProfile:
    record = _resolve_baseline(experiment_id)
    history = list_experiments()
    state = load_state() if state_exists() else None

    main_metric = state.main_metric if state and state.main_metric else _infer_metric(record)
    main_value = record.metrics.get(main_metric) if main_metric else None
    target = state.target_score if state else None
    target_gap = (target - main_value) if (target is not None and main_value is not None) else None

    domain = domain_for(
        state.task_type if state else None,
        state.project_type if state else None,
    )

    signals = [
        detect_imbalance(record, history),
        detect_metric_gap(record, history),
        detect_overfitting(record, history),
        detect_underfitting(record, history),
        detect_unstable_training(record, history),
    ]
    symptoms = [signal.name for signal in signals if signal.status == "detected"]
    symptoms.extend(_headroom_symptoms(domain, target_gap, symptoms, record, main_metric))

    techniques = techniques_for(domain, symptoms, limit=top_k)
    suggestions = [
        TechniqueSuggestion(
            technique_id=technique.technique_id,
            name=technique.name,
            category=technique.category,
            why=technique.why,
            expected_effect=technique.expected_effect,
            cost=technique.cost,  # type: ignore[arg-type]
            risk=technique.risk,  # type: ignore[arg-type]
            guardrails=list(technique.guardrails),
        )
        for technique in techniques
    ]
    do_not = [f"{anti.name} — {anti.reason}" for anti in antipatterns_for(symptoms)]

    profile = BaselineProfile(
        experiment_id=record.experiment_id or record.id,
        name=record.name,
        domain=domain,
        main_metric=main_metric,
        main_metric_value=main_value,
        target_score=target,
        target_gap=target_gap,
        headroom=_headroom(target_gap),
        bias_variance=_bias_variance(symptoms),
        readiness=_readiness(symptoms),
        detected_symptoms=symptoms,
        weak_classes=_weak_classes(record),
        data_quality_flags=_data_quality_flags(signals, record),
        standing=_standing(record, main_metric, main_value, target, target_gap),
        summary=_summary(record, symptoms, target_gap),
        recommended_techniques=suggestions,
        do_not_try_yet=do_not,
    )
    return profile


def write_baseline_profile_md(profile: BaselineProfile, output: Path | None = None) -> Path:
    output_path = output or BASELINE_PROFILE_MD
    lines = [
        f"# Baseline Profile - {profile.experiment_id}",
        "",
        f"> Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"> Domain: {profile.domain}",
        f"> Readiness: {profile.readiness}",
        "",
        "## 1. Standing",
        "",
        profile.standing,
        "",
        "## 2. Diagnosis",
        "",
        f"- Bias/variance: {profile.bias_variance}",
        f"- Headroom: {profile.headroom}"
        + (f" (target gap {profile.target_gap:+.3f})" if profile.target_gap is not None else ""),
        f"- Detected symptoms: {', '.join(profile.detected_symptoms) or 'none'}",
        "",
        profile.summary,
        "",
        "## 3. Weak Classes",
        "",
        *_weak_class_lines(profile.weak_classes),
        "",
        "## 4. Data-Quality Flags",
        "",
        *_bullets(profile.data_quality_flags or ["No structured data-quality risks detected."]),
        "",
        "## 5. Recommended Techniques (ranked)",
        "",
    ]
    if profile.recommended_techniques:
        for index, technique in enumerate(profile.recommended_techniques, start=1):
            lines.extend(
                [
                    f"### {index}. {technique.name}  "
                    f"`{technique.category}` (cost: {technique.cost}, risk: {technique.risk})",
                    "",
                    f"- Why: {technique.why}",
                    f"- Expected effect: {technique.expected_effect}",
                    *( [f"- Guardrail: {g}" for g in technique.guardrails] ),
                    "",
                ]
            )
    else:
        lines.extend(["_No technique matched; run error analysis first._", ""])
    lines.extend(
        [
            "## 6. Do Not Try Yet",
            "",
            *_bullets(profile.do_not_try_yet or ["No anti-pattern flagged for the current state."]),
            "",
            "## 7. Guardrails",
            "",
            "- Implement one controlled change before the next run.",
            "- Do not change the train/validation/test split unless that is the chosen direction.",
            "- Do not tune on the test set.",
            "- Re-profile after the next run with `octopus exp ingest` then `octopus exp profile`.",
            "",
        ]
    )
    atomic_write_text(output_path, "\n".join(lines))
    return output_path


# --- internals -------------------------------------------------------------


def _resolve_baseline(experiment_id: str | None) -> ExperimentRecord:
    if experiment_id:
        return load_experiment(experiment_id)
    baselines = [
        record
        for record in list_experiments()
        if record.kind == "baseline" and record.status == "completed"
    ]
    if not baselines:
        raise NoBaselineError(
            "No completed baseline experiment found. Log or ingest a baseline first."
        )
    metric = _infer_metric(baselines[0])
    with_metric = [record for record in baselines if metric in record.metrics]
    if with_metric:
        return max(with_metric, key=lambda record: record.metrics[metric])
    return baselines[-1]


def _infer_metric(record: ExperimentRecord) -> str:
    if state_exists():
        state = load_state()
        if state.main_metric:
            return state.main_metric
    for preferred in ("macro_f1", "accuracy", "f1", "recall_at_k", "rmse", "mae"):
        if preferred in record.metrics:
            return preferred
    return next(iter(record.metrics), "macro_f1")


def _headroom_symptoms(
    domain: str,
    target_gap: float | None,
    symptoms: list[str],
    record: ExperimentRecord,
    main_metric: str | None,
) -> list[str]:
    extra: list[str] = []
    if domain == DOMAIN_RAG and _looks_like_low_retrieval(record, main_metric, target_gap):
        extra.append(SYMPTOM_LOW_RETRIEVAL)
    if target_gap is not None:
        if 0 < target_gap <= SMALL_GAP:
            extra.append(SYMPTOM_NEAR_TARGET)
        elif target_gap > MODERATE_GAP:
            extra.append(SYMPTOM_LARGE_GAP)
    if not symptoms and not extra:
        extra.append(SYMPTOM_HEALTHY)
    return extra


def _looks_like_low_retrieval(
    record: ExperimentRecord, main_metric: str | None, target_gap: float | None
) -> bool:
    retrieval_keys = [
        value
        for key, value in record.metrics.items()
        if any(token in key.lower() for token in ("recall", "hit", "mrr", "ndcg"))
    ]
    if retrieval_keys and min(retrieval_keys) < LOW_RECALL_THRESHOLD:
        return True
    return target_gap is not None and target_gap > MODERATE_GAP


def _headroom(
    target_gap: float | None,
) -> Literal["at_or_above_target", "small", "moderate", "large", "no_target"]:
    if target_gap is None:
        return "no_target"
    if target_gap <= 0:
        return "at_or_above_target"
    if target_gap <= SMALL_GAP:
        return "small"
    if target_gap <= MODERATE_GAP:
        return "moderate"
    return "large"


def _bias_variance(
    symptoms: list[str],
) -> Literal["high_bias_underfit", "high_variance_overfit", "balanced", "undetermined"]:
    if "overfitting" in symptoms:
        return "high_variance_overfit"
    if "underfitting" in symptoms:
        return "high_bias_underfit"
    if SYMPTOM_NEAR_TARGET in symptoms or SYMPTOM_HEALTHY in symptoms:
        return "balanced"
    return "undetermined"


def _readiness(
    symptoms: list[str],
) -> Literal["no_baseline", "stabilize_baseline_first", "ready_to_tune"]:
    if "unstable_training" in symptoms or "underfitting" in symptoms:
        return "stabilize_baseline_first"
    return "ready_to_tune"


def _weak_classes(record: ExperimentRecord) -> list[WeakClass]:
    weak = [
        WeakClass(label=label, recall=metrics.recall, support=metrics.support)
        for label, metrics in record.per_class.items()
        if metrics.recall is not None and metrics.recall < LOW_RECALL_THRESHOLD
    ]
    return sorted(weak, key=lambda item: (item.recall if item.recall is not None else 1.0))


def _data_quality_flags(signals: list[DiagnosisSignal], record: ExperimentRecord) -> list[str]:
    detected = {signal.name for signal in signals if signal.status == "detected"}
    flags: list[str] = []
    if "metric_gap" in detected:
        flags.append(
            "Accuracy is much higher than macro F1 — majority-class bias or class imbalance."
        )
    if "overfitting" in detected:
        flags.append(
            "Large train/validation gap — verify the split for leakage or duplicates."
        )
    supports = [
        metrics.support
        for metrics in record.per_class.values()
        if metrics.support is not None and metrics.support > 0
    ]
    if supports and max(supports) / min(supports) >= 3:
        flags.append(
            f"Severe class support imbalance (support range {min(supports)}..{max(supports)})."
        )
    return flags


def _standing(
    record: ExperimentRecord,
    main_metric: str | None,
    main_value: float | None,
    target: float | None,
    target_gap: float | None,
) -> str:
    metric_text = (
        f"{main_metric}={main_value:g}" if main_value is not None else "no main metric recorded"
    )
    parts = [f"Baseline `{record.id}` ({record.name}) reached {metric_text}."]
    if target is not None and target_gap is not None:
        if target_gap <= 0:
            parts.append(f"It already meets the target ({main_metric}>={target:g}).")
        else:
            parts.append(f"It is {target_gap:+.3f} from the target of {target:g}.")
    else:
        parts.append("No target score is set, so headroom is unknown.")
    return " ".join(parts)


def _summary(record: ExperimentRecord, symptoms: list[str], target_gap: float | None) -> str:
    if not symptoms or symptoms == [SYMPTOM_HEALTHY]:
        return (
            "No strong failure signal in the baseline. Run error analysis to find the next "
            "controlled experiment instead of adding complexity."
        )
    named = ", ".join(symptom for symptom in symptoms if symptom != SYMPTOM_HEALTHY)
    return (
        f"The baseline shows: {named}. Address the highest-leverage, lowest-risk technique "
        "first and re-profile after one controlled run."
    )


def _weak_class_lines(weak_classes: list[WeakClass]) -> list[str]:
    if not weak_classes:
        return ["No per-class recall below threshold (or per-class metrics not available)."]
    return [
        f"- `{item.label}`: recall="
        + (f"{item.recall:g}" if item.recall is not None else "n/a")
        + (f", support={item.support}" if item.support is not None else "")
        for item in weak_classes
    ]


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None."]
