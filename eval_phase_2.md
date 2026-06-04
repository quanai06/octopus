# Octopus CLI Phase 2 Evaluation Report

## Metadata

- Date: 2026-06-04
- Repo: `/home/quan/octopus`
- Commit hash: `24ab2b00401a9128d3b71d48833b637d40ba61a4`
- Evaluator: Codex
- Python version: 3.12.7
- OS: Linux 6.19.11 arch1-1 x86_64
- Octopus version: 0.1.0 working tree
- Benchmark run directory: `/tmp/octopus-eval-phase2-20260604T031529Z`
- CLI used: `PYTHONPATH=src python -m octopus.cli.main`
- Guide used: `CODEX_EVAL_GUIDE.md`, extended with Phase 2 task/enforcement/code-context checks

## Executive Summary

- Final score: 100.0 / 100
- Status: Production-ready by the guide score scale
- Strongest dimensions: all dimensions passed in this run
- Weakest dimension: no failing dimension found in the deterministic Phase 2 benchmark
- Main improvement over Phase 1: baseline-first is now enforced by CLI behavior, not only by generated files

Top fixes completed since `eval.md`:

1. `octopus exp log` blocks main/candidate experiment logging until a completed baseline exists.
2. `.octopus/tasks.json` now tracks task state, while `tasks.md` is a synced readable view.
3. `octopus task start T020` is blocked until baseline task `T012` is completed by a real baseline log.
4. `octopus context` includes relevant code snippets while staying under the selected context budget in normal scenarios.
5. RAG planning now includes source citation, source hit rate, and faithfulness checks.

## Score Table

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| A Command Correctness | 20% | 100.0 | 20.0 |
| B Artifact Correctness | 20% | 100.0 | 20.0 |
| C Workflow Enforcement | 20% | 100.0 | 20.0 |
| D Context & Token Efficiency | 15% | 100.0 | 15.0 |
| E Output Quality | 15% | 100.0 | 15.0 |
| F Robustness & UX | 10% | 100.0 | 10.0 |
| Final | 100% | 100.0 | 100.0 |

## Scenario Results

| Scenario | Command | Artifact | Enforcement | Token | Quality | UX | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| S1 Text Classification | 100 | 100 | 100 | 100 | 100 | 100 | Pass |
| S2 Regression | 100 | 100 | 100 | 100 | 100 | 100 | Pass |
| S3 Image Classification | 100 | 100 | 100 | 100 | 100 | 100 | Pass |
| S4 RAG | 100 | 100 | 100 | 100 | 100 | 100 | Pass |

## Token Data

This run added small relevant code files to each scenario and verified that `octopus context` included code snippets under `## Relevant Code Context`.

| Scenario | Octopus tokens | Manual paste tokens | Saving % | Code context included? | Pass? |
|---|---:|---:|---:|---|---|
| S1 | 1,794 | 2,400 | 25.3% | Yes | Yes |
| S2 | 1,529 | 2,012 | 24.0% | Yes | Yes |
| S3 | 1,653 | 2,204 | 25.0% | Yes | Yes |
| S4 | 1,625 | 2,166 | 25.0% | Yes | Yes |

Token counts were measured with `octopus.context.token_estimator.estimate_tokens`.

## Enforcement Evidence

### Main model is blocked before baseline

In every scenario, `octopus exp log --kind main ...` exited with code `1` before a baseline was logged.

Example S1 output:

```text
Main model experiment blocked: no completed baseline found.
Start with a baseline and log it first:
  octopus exp log --kind baseline --name baseline --metric macro_f1=<value>
Then run: octopus task start T020
```

### T020 is blocked before baseline

In every scenario, `octopus task start T020` exited with code `1` before baseline completion.

Example S1 output:

```text
Task T020 is blocked.
Missing dependencies: T012
Log a completed baseline first:
  octopus exp log --kind baseline --name baseline --metric macro_f1=<value>
```

### Baseline log unblocks main model task

After this command:

```text
octopus exp log --kind baseline --name baseline_test --metric <main_metric>=0.0 --note "eval run"
```

the benchmark verified that `octopus task start T020` exited with code `0` in all scenarios.

Example S1 output:

```text
Task started: T020 Implement main model training
```

## Findings

### What works well

- Standard command flow passed for all scenarios: `init`, `plan`, `ml-plan`, `tasks`, `task next`, `context`, `exp log`, `sync`, and `status`.
- Runtime files follow runtime config:
  - `claude,codex` scenarios generated both `CLAUDE.md` and `AGENTS.md`.
  - `claude`-only scenarios did not generate `AGENTS.md`.
- `.octopus/tasks.json` exists in all scenarios and is the managed task source of truth.
- `tasks.md` remains agent-readable but no longer has to be edited manually as the only task state.
- `octopus context` includes selected planning sections plus relevant code snippets.
- Low-budget context behavior prints a budget warning when fixed overhead exceeds the requested budget.
- RAG output quality improved: source citations, source hit rate, retrieval-only evaluation, chunking, embedding, hallucination, and faithfulness are all present.

### Bugs found

No blocking bugs were found in this deterministic Phase 2 run.

Residual risk:

- The benchmark uses local module execution because `cli-octopus` was intentionally uninstalled after the previous evaluation. Installed-console-script behavior should still be tested before release with `pip install -e ".[dev]"`.
- Code-context relevance is heuristic. It worked for controlled files, but larger repos may need better ranking or explicit `--include` paths.
- A perfect score here means the current benchmark passed; it does not prove all real-world ML workflows are covered.

### Token/context issues

- No token regression was observed. Context still saved about 24-25% compared with manual paste while adding code snippets.
- The current benchmark counts manual paste as planning docs only. If manual paste also included code files, Octopus context would save more.

### Baseline enforcement issues

- The Phase 1 gap is fixed for this benchmark: main model experiment logging is now blocked before a completed baseline.
- Task workflow is also enforced: `T020` cannot start until `T012` is complete, and `T012` cannot be manually completed without a real baseline experiment.

## Verification Commands

```text
PYTHONPATH=src pytest -q
49 passed in 1.26s

ruff check .
All checks passed!

PYTHONPATH=src mypy src
Success: no issues found in 39 source files

PYTHONPATH=src python -m octopus.cli.main --help
OK; includes exp and task commands
```

## Recommended Fix Priority

| Priority | Area | Issue | Why it matters | Suggested fix |
|---:|---|---|---|---|
| P1 | Packaging eval | This run used module execution, not installed `octopus` command | Release users run the console script | Add CI job that installs with `pip install -e ".[dev]"` and runs the same benchmark |
| P1 | Benchmark automation | Phase 2 benchmark is still an ad hoc script under `/tmp` | Future regressions need repeatable checks | Promote this scenario runner into `tests/benchmark/` |
| P2 | Code context ranking | Relevant-code selection is heuristic | Large repos may include weak snippets | Add `--include`, `--exclude`, and task-aware file weights |
| P2 | Task workflow | Task graph is static | Real projects may need custom tasks | Add `octopus task add`, `octopus task depend`, and milestone editing |

## Regression Baseline

Save this report as the Phase 2 baseline for future comparison.

```text
Current score: 100.0 / 100
Target beta score: >= 70
Target production score: >= 85
```

## Recommended GitHub Issues

1. Add installed-console-script benchmark job for `octopus`.
2. Move the Phase 2 benchmark runner into `tests/benchmark/`.
3. Add explicit code-context include/exclude controls.
4. Add task graph editing commands for custom project workflows.

## Raw Benchmark Data

This section is intentionally explicit. Future eval markdown reports should keep raw counts,
exit codes, token counts, and pass/fail evidence instead of only reporting summaries.

### Scenario Directories

| Scenario | Directory |
|---|---|
| S1 | `/tmp/octopus-eval-phase2-20260604T031529Z/s1` |
| S2 | `/tmp/octopus-eval-phase2-20260604T031529Z/s2` |
| S3 | `/tmp/octopus-eval-phase2-20260604T031529Z/s3` |
| S4 | `/tmp/octopus-eval-phase2-20260604T031529Z/s4` |

### Checklist Counts

| Scenario | A Command | B Artifact | C Enforcement | D Context | E Quality | F UX |
|---|---:|---:|---:|---:|---:|---:|
| S1 | 10/10 | 13/13 | 10/10 | 10/10 | 8/8, 0 forbidden | 10/10 |
| S2 | 10/10 | 13/13 | 10/10 | 10/10 | 6/6, 0 forbidden | 10/10 |
| S3 | 10/10 | 13/13 | 10/10 | 10/10 | 6/6, 0 forbidden | 10/10 |
| S4 | 10/10 | 13/13 | 10/10 | 10/10 | 7/7, 0 forbidden | 10/10 |

### Command Exit Codes

Expected exits:

- Normal workflow commands should exit `0`.
- `task_start_t020_before` should exit `1` because `T020` is blocked before baseline.
- `exp_main_before` should exit `1` because main model logging is blocked before baseline.

| Scenario | init | plan | ml-plan | tasks | task next | task start T020 before | context | exp main before | exp baseline log | task start T020 after | sync | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| S2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| S3 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| S4 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |

### Token Measurements

| Scenario | Context tokens | Context command estimate | Manual planning-doc tokens | Delta tokens | Saving % |
|---|---:|---:|---:|---:|---:|
| S1 | 1,794 | 1,794 | 2,400 | 606 | 25.25% |
| S2 | 1,529 | 1,530 | 2,012 | 483 | 24.01% |
| S3 | 1,653 | 1,654 | 2,204 | 551 | 25.00% |
| S4 | 1,625 | 1,626 | 2,166 | 541 | 24.98% |

Manual planning-doc tokens are measured from:

```text
requirements.md
ml_design.md
experiment_plan.md
data_strategy.md
compute_budget.md
tasks.md
```

Octopus context tokens are measured from:

```text
.octopus/context/current_context.md
```

The context output was also checked for:

```text
## Relevant Code Context
src/
```

### Quality Checks

| Scenario | Must-have checks passed | Forbidden hits |
|---|---|---|
| S1 | TF-IDF/bag-of-words/logistic/LinearSVC; macro F1; per-class recall/confusion matrix; imbalance; stratified split; duplicate/leakage; Vietnamese/social media noise; baseline | none |
| S2 | Linear Regression/simple tree; MAE/RMSE; train/validation/test; preprocessing/feature/residual note; outlier/skew; CPU/local | none |
| S3 | transfer learning/ResNet/MobileNet/pretrained; split; augmentation; macro F1/per-class recall; smoke test; overfitting | none |
| S4 | BM25; Recall@k/MRR/source hit; chunking; embedding; citation/source; retrieval evaluation set; hallucination/faithfulness | none |

### UX/Robustness Checks

| Check | Result |
|---|---|
| F1 plan before state friendly | pass |
| F2 ml-plan software graceful | pass |
| F3 context before plan files actionable | pass |
| F6 init rerun no silent destroy | pass |
| F7 help major commands | pass |
| F8 Rich/readable output | pass |
| F9 missing optional fields no crash | pass |
| F10 unknown task fallback | pass |
| F11 task next actionable | pass |
| F12 task done T012 enforces baseline | pass |
