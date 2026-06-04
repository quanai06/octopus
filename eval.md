# Octopus CLI Evaluation Report

## Metadata

- Date: 2026-06-04
- Repo: `/home/quan/octopus`
- Commit hash: `24ab2b00401a9128d3b71d48833b637d40ba61a4`
- Evaluator: Codex
- Python version: 3.12.7
- OS: Linux 6.19.11 arch1-1 x86_64
- Octopus version: 0.1.0
- Benchmark run directory: `/tmp/octopus-eval-20260604T024903Z`
- Guide used: `CODEX_EVAL_GUIDE.md`

## Executive Summary

- Final score: 95.4 / 100
- Status: Production-ready by the guide score scale
- Strongest dimensions: Command Correctness, Artifact Correctness, Robustness & UX
- Weakest dimension: Context & Token Efficiency, mainly because low-budget context does not explicitly warn when the final context still exceeds the requested budget
- Top 3 fixes:
  1. Add a hard workflow guard or warning when `octopus exp log` records a main/candidate model before a baseline exists.
  2. Make RAG artifacts explicitly require source citations and faithfulness checks.
  3. Improve `octopus context --budget` output so it clearly reports when header/task overhead still exceeds the budget.

## Score Table

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| A Command Correctness | 20% | 100.0 | 20.0 |
| B Artifact Correctness | 20% | 100.0 | 20.0 |
| C Workflow Enforcement | 20% | 90.0 | 18.0 |
| D Context & Token Efficiency | 15% | 88.9 | 13.3 |
| E Output Quality | 15% | 93.9 | 14.1 |
| F Robustness & UX | 10% | 100.0 | 10.0 |
| Final | 100% | 95.4 | 95.4 |

## Scenario Results

| Scenario | Command | Artifact | Enforcement | Token | Quality | UX | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| S1 Text Classification | 100 | 100 | 90 | 88.9 | 100.0 | 100 | Pass |
| S2 Regression | 100 | 100 | 90 | 88.9 | 100.0 | 100 | Pass |
| S3 Image Classification | 100 | 100 | 90 | 88.9 | 100.0 | 100 | Pass |
| S4 RAG | 100 | 100 | 90 | 88.9 | 75.7 | 100 | Pass with quality gaps |

## Token Data

| Scenario | Octopus tokens | Manual paste tokens | Saving % | Pass? |
|---|---:|---:|---:|---|
| S1 | 1,680 | 2,256 | 25.5% | Yes |
| S2 | 1,417 | 1,876 | 24.5% | Yes |
| S3 | 1,532 | 2,063 | 25.7% | Yes |
| S4 | 1,446 | 1,911 | 24.3% | Yes |

Token counts were measured with `octopus.context.token_estimator.estimate_tokens`, which uses `tiktoken` when available and falls back to character-based estimation on failure.

## Findings

### What works well

- All required command flows passed in all four scenarios: `init`, `plan`, `ml-plan`, `tasks`, `context`, `exp log`, `sync`, and `status`.
- Generated files matched runtime rules. `claude,codex` scenarios generated both `CLAUDE.md` and `AGENTS.md`; `claude`-only scenarios did not generate `AGENTS.md`.
- Baseline ordering is strong in generated plans: `T010` appears before `T020`, and `T020` depends on `T012`.
- Scenario-specific planning is generally correct:
  - S1 uses TF-IDF Logistic Regression/LinearSVC, macro F1, per-class recall, stratified split, duplicate leakage checks, and imbalance handling.
  - S2 uses Linear Regression/tree baselines, MAE/RMSE, CPU/local compute, outlier and skew notes.
  - S3 uses transfer learning, GPU-aware compute, smoke tests, augmentation, overfitting risk, and macro F1/per-class recall.
  - S4 uses BM25, dense retrieval, Recall@k/MRR/nDCG, chunking, and hallucination risk.
- Existing unit tests pass: `42 passed in 1.10s`.

### Bugs found

- `octopus exp log` does not enforce baseline-first logging. In a fresh S1 project, this command succeeded:

```text
octopus exp log --name phobert_main --model phobert-base --metric macro_f1=0.5
Experiment logged.
ID: exp_002
Name: phobert_main
```

Expected behavior from the guide: warn or block when logging a main model before a baseline.

- `octopus context --budget 50` skipped all planning sections due to budget, but still produced a 174-token context without an explicit exceeded-budget warning:

```text
Tokens: 174
Skipped:
  requirements.md#Dataset (budget)
  ...
```

### Weak output sections

- RAG planning should explicitly require source citations in answers. Current S4 output has `answer_with_source` as the output type, but does not clearly instruct the user to cite retrieved source documents.
- RAG planning should include faithfulness/source-grounding checks, not only retrieval ranking metrics.
- RAG `Experiment 3: Candidate model` repeats `BM25`, which makes the candidate step less useful.

### Token/context issues

- Normal training context is smaller than manual paste in every scenario, saving about 24-26%.
- Low-budget context handling is recoverable but under-explained. It shows skipped sections, but not a clear "budget exceeded" state when the final context remains above budget because of fixed overhead.

### Baseline enforcement issues

- Artifact-level baseline enforcement is good.
- Runtime experiment logging enforcement is incomplete. The product can tell agents not to skip baseline, but the CLI itself still allows main-model experiment records before baseline records.

## Recommended Fix Priority

| Priority | Area | Issue | Why it matters | Suggested fix |
|---:|---|---|---|---|
| P0 | Workflow enforcement | `exp log` allows main/candidate model before baseline | This is the main product promise and the guide's most important dimension | Detect main-model names/models or add `--kind baseline/main`; warn or block if no completed baseline experiment exists |
| P1 | RAG output quality | Missing explicit source citation and faithfulness requirements | RAG users need grounded answers, not just high retrieval recall | Add citation/source-grounding requirements to RAG templates and metrics |
| P1 | Context UX | Low budget can produce context above budget without a clear warning | Users may assume the budget was respected | Add token status `warning/exceeded` to context output when final tokens exceed requested budget |
| P2 | RAG experiment planning | Candidate model repeats BM25 | Makes the RAG experiment queue less actionable | Use BM25 as baseline, dense retrieval as candidate, reranker/generator only after retrieval baseline |
| P2 | Benchmark automation | Guide recommends `tests/benchmark/`, but this run only created a report | Future regressions need automated checks | Add scenario fixtures and deterministic benchmark tests under `tests/benchmark/` |

## Regression Baseline

Save this report as the baseline for future comparison.

```text
Current score: 95.4 / 100
Target beta score: >= 70
Target production score: >= 85
```

## Recommended GitHub Issues

1. Enforce baseline-first experiment logging in `octopus exp log`.
2. Add RAG source citation and faithfulness requirements to generated planning artifacts.
3. Improve context budget warning when selected context exceeds the requested budget.
4. Fix RAG candidate experiment queue so it does not repeat BM25 as both baseline and candidate.
5. Add reproducible benchmark tests under `tests/benchmark/` based on `CODEX_EVAL_GUIDE.md`.
