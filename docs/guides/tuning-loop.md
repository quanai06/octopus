# The tuning loop

After a baseline is logged, improve it with one disciplined change at a time.

```text
ingest → profile → next → choose → context → implement ONE change → ingest → repeat
```

## 1. Profile the baseline

```bash
octopus exp profile                 # best baseline; or --exp E001
octopus exp profile --top-k 3       # fewer techniques
```

Writes `.octopus/reports/baseline_profile.md`:

- standing vs target, headroom (small / moderate / large);
- bias/variance (overfit / underfit / balanced);
- weak classes (low per-class recall) or low retrieval metrics;
- data-quality flags (e.g. accuracy ≫ macro-F1 → imbalance/leakage risk);
- **ranked techniques** (cost/risk-ordered) with guardrails;
- a **Do Not Try Yet** list (anti-patterns for the current symptoms).

Recommendations are domain-aware: classification, regression, and rag/retrieval
draw from different technique sets.

## 2. Get ranked next directions

```bash
octopus exp next                    # or --top-k N
```

Writes `.octopus/plans/next_steps.{md,yaml}` — symptom-level directions filled
with concrete techniques from the library, each with rationale, evidence,
confidence/risk/cost, guardrails, and a stop condition.

## 3. Choose one and build its context

```bash
octopus exp choose D1
octopus context --direction D1 --target claude     # or --target codex
```

This produces a small, direction-specific context (just the selected step,
evidence, guardrails, and relevant code) instead of the whole planning history.

## 4. Implement, ingest, re-profile

Implement **only** the top-ranked technique for that direction. Then:

```bash
octopus exp ingest --run-dir runs/<new_run>
octopus exp profile
```

Compare against the current best and repeat. Guardrails enforced throughout: one
change per run, no split changes, no test-set tuning.
