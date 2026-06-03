# CLI Octopus — Phase 1 MVP Specification

> **Version:** 1.1.0
> **Status:** Ready to implement
> **Last updated:** 2026-06-03

---

## Table of Contents

1. [Mục tiêu Phase 1](#1-mục-tiêu-phase-1)
2. [Tech Stack](#2-tech-stack)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Storage Strategy](#4-storage-strategy)
5. [Internal Schemas](#5-internal-schemas)
6. [Jinja2 Templates](#6-jinja2-templates)
7. [Commands](#7-commands)
8. [Precondition Guards](#8-precondition-guards)
9. [Error Handling](#9-error-handling)
10. [Token Management](#10-token-management)
11. [Test Plan](#11-test-plan)
12. [Acceptance Criteria](#12-acceptance-criteria)
13. [Demo cuối Phase 1](#13-demo-cuối-phase-1)
14. [Scope không làm Phase 1](#14-scope-không-làm-phase-1)

---

## 1. Mục tiêu Phase 1

Phase 1 xây dựng phiên bản MVP chạy được thật của `cli-octopus`.

**Mục tiêu chính:**

- Tạo CLI cho project ML/DL với interactive planning flow
- Hỏi requirement có cấu trúc, phân nhóm rõ ràng
- Sinh các file planning chuẩn từ Jinja2 templates
- Sinh context gọn cho Claude Code / Codex với token estimate
- Giảm việc copy-paste prompt dài vào chat AI
- Chặn user train model khi chưa có plan rõ ràng

**Phase này chưa làm:**

- MCP server
- Vector database / Semantic memory
- MLflow / W&B integration
- Web UI / Dashboard
- Auto training / AutoML
- Multi-agent orchestration
- GitHub / HuggingFace integration

---

## 2. Tech Stack

### Core dependencies

| Thành phần      | Thư viện              | Mục đích                                      |
|-----------------|-----------------------|-----------------------------------------------|
| Language        | Python 3.11+          | Ngôn ngữ chính                                |
| Package manager | uv                    | Quản lý package, venv, lock file              |
| CLI framework   | Typer                 | Xây CLI command                               |
| Terminal UI     | Rich                  | Bảng, panel, progress, prompt đẹp             |
| Interactive     | questionary           | Multi-choice, confirm, fuzzy select           |
| Schema          | Pydantic v2           | Validate dữ liệu requirement / task           |
| Template engine | Jinja2                | Render file markdown từ template              |
| Config          | PyYAML                | Đọc / ghi `.octopus/config.yaml`              |
| Storage         | JSON (stdlib)         | Lưu `project_state.json` — source of truth   |
| Token estimate  | tiktoken              | Ước lượng token context                       |
| Ignore files    | pathspec              | Đọc `.gitignore`, bỏ qua file rác            |
| Testing         | pytest                | Viết test                                     |
| Lint / format   | ruff                  | Format và lint code                           |

> **Lưu ý:** SQLite / SQLModel bị loại khỏi Phase 1. Lý do: Phase 1 chưa cần query hay history tracking. JSON đủ dùng và đơn giản hơn. SQLModel sẽ vào Phase 2 khi làm experiment tracking.

> **Thêm mới:** `questionary` — thư viện interactive prompt với arrow-key selection, multi-select, confirm, cần thiết để `octopus ask` không hỏi 20 câu plain text liên tục.

### `pyproject.toml`

```toml
[project]
name = "cli-octopus"
version = "0.1.0"
description = "A CLI project brain for ML/DL engineers: plan experiments, compress context, and prepare Claude/Codex-ready project instructions before training or coding."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "questionary>=2.0",
    "pydantic>=2",
    "pyyaml>=6",
    "jinja2>=3",
    "tiktoken>=0.7",
    "pathspec>=0.12",
]

[project.scripts]
octopus = "octopus.cli.main:app"

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-mock",
    "ruff",
    "mypy",
]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### Khởi tạo môi trường

```bash
uv init cli-octopus
cd cli-octopus
uv venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows

uv add typer rich questionary pydantic pyyaml jinja2 tiktoken pathspec
uv add --dev pytest pytest-mock ruff mypy
```

---

## 3. Cấu trúc thư mục

```
cli-octopus/
├── pyproject.toml
├── README.md
│
├── src/
│   └── octopus/
│       ├── __init__.py
│       │
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py                  # Typer app root, register all commands
│       │   └── commands/
│       │       ├── __init__.py
│       │       ├── init.py              # octopus init
│       │       ├── ask.py               # octopus ask
│       │       ├── plan.py              # octopus plan
│       │       ├── ml_plan.py           # octopus ml-plan
│       │       ├── tasks.py             # octopus tasks
│       │       ├── context.py           # octopus context
│       │       ├── sync.py              # octopus sync
│       │       └── status.py            # octopus status
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py                # Load / save config.yaml
│       │   ├── paths.py                 # Centralize all path constants
│       │   ├── schemas.py               # Pydantic models
│       │   └── guards.py                # Precondition check functions
│       │
│       ├── planners/
│       │   ├── __init__.py
│       │   ├── requirement_planner.py   # Render requirements.md
│       │   ├── ml_planner.py            # Render ml_design.md + experiment_plan.md
│       │   └── task_planner.py          # Render tasks.md
│       │
│       ├── context/
│       │   ├── __init__.py
│       │   ├── builder.py               # Assemble context từ plan files
│       │   ├── token_estimator.py       # tiktoken wrapper + warn thresholds
│       │   └── file_scanner.py          # Scan files, apply gitignore rules
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   └── state_store.py           # Read / write project_state.json
│       │
│       └── templates/
│           ├── requirements.md.j2
│           ├── ml_design.md.j2
│           ├── experiment_plan.md.j2
│           ├── tasks.md.j2
│           ├── CLAUDE.md.j2
│           └── AGENTS.md.j2
│
└── tests/
    ├── conftest.py
    ├── test_init.py
    ├── test_ask.py
    ├── test_ml_plan.py
    ├── test_context.py
    ├── test_guards.py
    └── test_token_estimator.py
```

### `core/paths.py` — tập trung path constants

```python
from pathlib import Path

OCTOPUS_DIR      = Path(".octopus")
CONFIG_FILE      = OCTOPUS_DIR / "config.yaml"
STATE_FILE       = OCTOPUS_DIR / "project_state.json"
CONTEXT_DIR      = OCTOPUS_DIR / "context"
CURRENT_CONTEXT  = CONTEXT_DIR / "current_context.md"
EXPERIMENTS_DIR  = OCTOPUS_DIR / "experiments"
ADR_DIR          = OCTOPUS_DIR / "adr"

REQUIREMENTS_MD  = Path("requirements.md")
ML_DESIGN_MD     = Path("ml_design.md")
EXPERIMENT_MD    = Path("experiment_plan.md")
TASKS_MD         = Path("tasks.md")
CLAUDE_MD        = Path("CLAUDE.md")
AGENTS_MD        = Path("AGENTS.md")
```

---

## 4. Storage Strategy

Phase 1 chỉ dùng **JSON file** làm source of truth. Không dùng SQLite.

### Cấu trúc `.octopus/`

```
.octopus/
├── config.yaml          # Project config (runtime, created_at, version)
├── project_state.json   # Full project state — source of truth
├── context/
│   └── current_context.md
├── experiments/         # Reserved for Phase 2
└── adr/                 # Reserved for Phase 2
```

### `.octopus/config.yaml`

```yaml
version: "0.1.0"
runtime:
  - claude
  - codex
created_at: "2026-06-03T10:00:00"
last_updated: "2026-06-03T10:00:00"
```

### `state_store.py` interface

```python
from pathlib import Path
from octopus.core.schemas import ProjectState

def load_state() -> ProjectState:
    """Load state từ project_state.json. Raise FileNotFoundError nếu chưa có."""

def save_state(state: ProjectState) -> None:
    """Ghi state ra project_state.json (atomic write qua temp file)."""

def state_exists() -> bool:
    """Check xem project_state.json đã tồn tại chưa."""

def merge_state(updates: dict) -> ProjectState:
    """Load state hiện tại, merge updates, save lại. Dùng cho octopus ask lần 2."""
```

> **Atomic write:** Ghi ra `.octopus/project_state.json.tmp` trước, sau đó rename để tránh corrupt nếu bị interrupt.

---

## 5. Internal Schemas

### `ProjectState`

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class ComputeConfig(BaseModel):
    has_gpu: bool = False
    environment: str | None = None          # "local", "colab_t4", "colab_a100", "kaggle", "server"
    budget_note: str | None = None
    deadline: str | None = None             # ISO date string, optional


class ProjectState(BaseModel):
    project_name: str
    project_goal: str | None = None
    target_users: str | None = None
    project_type: Literal["software", "ml", "dl", "rag", "research"]
    task_type: str | None = None            # "text_classification", "regression", etc.
    input_type: str | None = None           # "text", "image", "tabular", etc.
    output_type: str | None = None
    dataset_status: Literal["available", "partial", "not_ready"] | None = None
    dataset_size_note: str | None = None    # Free text, e.g. "~50k samples"
    has_labels: bool | None = None
    has_class_imbalance: bool | None = None
    main_metric: str | None = None
    target_score: float | None = None       # Optional target score
    baseline_required: bool = True
    runtime: list[str] = Field(default_factory=list)   # ["claude", "codex"]
    compute: ComputeConfig = Field(default_factory=ComputeConfig)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
```

### `TaskItem`

```python
from pydantic import BaseModel
from typing import Literal


class TaskItem(BaseModel):
    id: str                                         # "T001", "T002", ...
    title: str
    priority: Literal["high", "medium", "low"]
    status: Literal["todo", "in_progress", "done"] = "todo"
    depends_on: list[str] = []
    milestone: str | None = None
    description: str | None = None
```

### `ContextBuildResult`

```python
from pydantic import BaseModel


class ContextBuildResult(BaseModel):
    task: str
    output_path: str
    estimated_tokens: int
    token_status: str                    # "ok", "warning", "exceeded"
    included_files: list[str]
    excluded_files: list[str]
    excluded_patterns: list[str]
```

---

## 6. Jinja2 Templates

Tất cả templates nằm trong `src/octopus/templates/`. Các biến được inject từ `ProjectState`.

### `requirements.md.j2`

```jinja2
# Requirements — {{ project_name }}

> Generated by Octopus CLI v{{ octopus_version }} on {{ generated_at }}

---

## Project Goal

{{ project_goal | default("_To be defined._") }}

## Target Users

{{ target_users | default("_To be defined._") }}

## Problem Type

- **Category:** {{ project_type | upper }}
{% if task_type %}
- **Task:** {{ task_type }}
{% endif %}
{% if input_type %}
- **Input:** {{ input_type }}
{% endif %}
{% if output_type %}
- **Output:** {{ output_type }}
{% endif %}

## Dataset

- **Status:** {{ dataset_status | default("unknown") }}
{% if dataset_size_note %}
- **Size:** {{ dataset_size_note }}
{% endif %}
{% if has_labels is not none %}
- **Labels:** {{ "Available" if has_labels else "Not available" }}
{% endif %}
{% if has_class_imbalance is not none %}
- **Class imbalance:** {{ "Yes — handle in training strategy" if has_class_imbalance else "No" }}
{% endif %}

## Evaluation

- **Main metric:** {{ main_metric | default("_To be defined._") }}
{% if target_score %}
- **Target score:** {{ target_score }}
{% endif %}

## Compute

- **GPU:** {{ "Yes" if compute.has_gpu else "No" }}
{% if compute.environment %}
- **Environment:** {{ compute.environment }}
{% endif %}
{% if compute.deadline %}
- **Deadline:** {{ compute.deadline }}
{% endif %}

## Functional Requirements

_To be filled by the team._

## Non-functional Requirements

_To be filled by the team._

## Constraints

_To be filled by the team._

## Assumptions

_To be filled by the team._

## Risks

_To be filled by the team._

## Success Criteria

_To be filled by the team._
```

---

### `ml_design.md.j2`

```jinja2
# ML Design — {{ project_name }}

> Generated by Octopus CLI v{{ octopus_version }} on {{ generated_at }}

---

## Problem Framing

- **Task type:** {{ task_type }}
- **Input:** {{ input_type }}
- **Output:** {{ output_type }}

## Dataset Strategy

- **Status:** {{ dataset_status }}
{% if has_class_imbalance %}
- ⚠️ Class imbalance detected — consider oversampling, class weights, or stratified split.
{% endif %}

## Baseline Models

{% for model in baseline_models %}
- {{ model }}
{% endfor %}

## Candidate Models

_To be filled after baseline is established._

## Evaluation Metrics

{% for metric in metrics %}
- {{ metric }}
{% endfor %}

## Training Strategy

- Always train baseline before main model.
- Log every experiment result, even failed ones.
{% if compute.has_gpu %}
- GPU available: {{ compute.environment }}.
{% else %}
- ⚠️ No GPU detected — limit model size accordingly.
{% endif %}

## Known Risks

{% for risk in risks %}
- ⚠️ {{ risk }}
{% endfor %}

## Compute Budget

{% if compute.budget_note %}
{{ compute.budget_note }}
{% else %}
_Not specified._
{% endif %}

## Recommended First Experiment

{{ first_experiment_note }}
```

---

### `experiment_plan.md.j2`

```jinja2
# Experiment Plan — {{ project_name }}

> Generated by Octopus CLI v{{ octopus_version }} on {{ generated_at }}

---

## Goal

Establish a reproducible baseline before exploring advanced models.

## Baseline Experiment

| Field       | Value                              |
|-------------|------------------------------------|
| Model       | {{ baseline_models[0] }}           |
| Metric      | {{ main_metric }}                  |
| Dataset     | Full train set with stratified split |
| Status      | ☐ Not started                     |

## Experiment Queue

| ID   | Model                    | Priority | Depends On | Status      |
|------|--------------------------|----------|------------|-------------|
| E001 | {{ baseline_models[0] }} | High     | —          | ☐ Todo      |
{% if baseline_models | length > 1 %}
| E002 | {{ baseline_models[1] }} | High     | E001       | ☐ Todo      |
{% endif %}
| E003 | _Main model TBD_         | Medium   | E001       | ☐ Todo      |

## Metrics to Track

{% for metric in metrics %}
- {{ metric }}
{% endfor %}
- Training time (seconds)
- Inference time per sample (ms)

## Logging Format

```json
{
  "experiment_id": "E001",
  "model": "{{ baseline_models[0] }}",
  "{{ main_metric }}": null,
  "train_time_sec": null,
  "notes": ""
}
```

## Stop Condition

- Reached target score: {{ target_score | default("not set") }}
- Or exhausted compute budget

## Next Decision Rules

- If baseline {{ main_metric }} < expected → check data quality first
- If baseline {{ main_metric }} >= expected → move to E003 (main model)
- Always document why an experiment was stopped or skipped
```

---

### `tasks.md.j2`

```jinja2
# Tasks — {{ project_name }}

> Generated by Octopus CLI v{{ octopus_version }} on {{ generated_at }}

---

## Milestone 1: Project Setup

- [ ] T001: Initialize repo and environment
  - Priority: High | Depends on: — 
- [ ] T002: Define config and project structure
  - Priority: High | Depends on: T001

## Milestone 2: Data Pipeline

- [ ] T003: Load and inspect dataset
  - Priority: High | Depends on: T001
- [ ] T004: Validate schema and check for issues
  - Priority: High | Depends on: T003
- [ ] T005: Create train / val / test split
  - Priority: High | Depends on: T004
{% if has_class_imbalance %}
- [ ] T006: Handle class imbalance (oversampling / class weights)
  - Priority: High | Depends on: T005
{% endif %}

## Milestone 3: Baseline

- [ ] T010: Implement baseline model ({{ baseline_models[0] }})
  - Priority: High | Depends on: T005
- [ ] T011: Evaluate baseline on val set
  - Priority: High | Depends on: T010
- [ ] T012: Log baseline results to `.octopus/experiments/`
  - Priority: High | Depends on: T011

## Milestone 4: Main Model

- [ ] T020: Implement main model training
  - Priority: Medium | Depends on: T012
- [ ] T021: Run first experiment and compare with baseline
  - Priority: Medium | Depends on: T020
- [ ] T022: Update experiment_plan.md with results
  - Priority: Medium | Depends on: T021

## Milestone 5: Review

- [ ] T030: Error analysis on val set
  - Priority: Medium | Depends on: T021
- [ ] T031: Suggest next experiment
  - Priority: Low | Depends on: T030
- [ ] T032: Update tasks.md with current status
  - Priority: Low | Depends on: —
```

---

### `CLAUDE.md.j2`

```jinja2
# Claude Instructions — {{ project_name }}

This project uses **Octopus CLI** for planning and context management.

---

## Before Starting Any Task

1. Read `requirements.md` — understand the goal and constraints.
2. Read `tasks.md` — find the current active task.
3. Read `.octopus/context/current_context.md` — this is your working context.
{% if project_type in ["ml", "dl", "rag"] %}
4. Read `ml_design.md` and `experiment_plan.md` — understand the ML strategy.
{% endif %}

## Rules

- **Do not** train a model without checking `experiment_plan.md` first.
- **Do not** change architecture without creating an ADR in `.octopus/adr/`.
- **Do not** load raw datasets or checkpoint files into context.
- **Do not** implement a new experiment before baseline is logged.
- After completing a task, update its status in `tasks.md`.
{% if project_type in ["ml", "dl"] %}
- Log all experiment metrics into `.octopus/experiments/` in JSON format.
{% endif %}

## Context File

Your primary working context is:

```
.octopus/context/current_context.md
```

If you need more context, ask the user to run:

```bash
octopus context --task "<task description>"
```

## Runtime

Generated for: **Claude Code**
```

---

### `AGENTS.md.j2`

```jinja2
# Agent Instructions — {{ project_name }}

This project uses **Octopus CLI** for planning and context management.

---

## Before Coding

1. Read `requirements.md`.
2. Read `tasks.md` — identify the current active task.
3. Read `.octopus/context/current_context.md`.
{% if project_type in ["ml", "dl", "rag"] %}
4. Read `ml_design.md` and `experiment_plan.md`.
{% endif %}

## Development Rules

- Follow the current task context strictly.
- Keep changes minimal and task-focused.
- Do not introduce a new architecture without an ADR.
- Do not run training before a baseline and metric are defined.
- Update task status in `tasks.md` after implementation.

## Context Refresh

```bash
octopus context --task "<task description>"
```

## Runtime

Generated for: **Codex / OpenAI Agents**
```

---

## 7. Commands

Phase 1 gồm **8 commands:**

```bash
octopus init
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus context
octopus sync
octopus status        # Thêm mới
```

---

### 7.1. `octopus init`

**Mục tiêu:** Khởi tạo project Octopus.

**Usage:**

```bash
octopus init
octopus init --runtime claude,codex
```

**Precondition:** Không có — đây là command khởi đầu.

**Logic:**

1. Kiểm tra `.octopus/` đã tồn tại chưa. Nếu có → hỏi confirm overwrite.
2. Tạo thư mục `.octopus/`, `context/`, `experiments/`, `adr/`.
3. Tạo `config.yaml` với runtime từ flag.
4. Tạo các file markdown rỗng (dùng template render với empty state).
5. Tạo `CLAUDE.md` nếu runtime có `claude`.
6. Tạo `AGENTS.md` nếu runtime có `codex`.
7. In summary.

**Output files:**

```
.octopus/config.yaml
.octopus/project_state.json       ← chưa có, tạo skeleton rỗng
requirements.md
ml_design.md
experiment_plan.md
tasks.md
CLAUDE.md                         ← nếu runtime claude
AGENTS.md                         ← nếu runtime codex
```

**Terminal output:**

```
🐙 Octopus initialized successfully.

Created:
  .octopus/config.yaml
  requirements.md
  ml_design.md
  experiment_plan.md
  tasks.md
  CLAUDE.md
  AGENTS.md

Next step:
  octopus ask
```

---

### 7.2. `octopus ask`

**Mục tiêu:** Thu thập project requirements qua interactive prompts có cấu trúc.

**Usage:**

```bash
octopus ask
octopus ask --reset       # Bỏ qua state cũ, hỏi lại từ đầu
```

**Precondition:** `.octopus/config.yaml` phải tồn tại (đã chạy `octopus init`).

**Behavior khi chạy lại:**

- Nếu `project_state.json` đã tồn tại và không có `--reset` → **merge mode**: show giá trị cũ làm default, user có thể Enter để giữ nguyên hoặc nhập mới.
- Nếu có `--reset` → hỏi lại từ đầu, ghi đè.

**UX:** Dùng `questionary` + `Rich` panel. Các câu hỏi chia thành 4 nhóm rõ ràng, in header nhóm trước mỗi nhóm. Câu optional có thể bỏ qua bằng Enter.

**Nhóm 1 — Project Overview**

| Câu hỏi | Type | Required |
|---|---|---|
| Tên project? | text | ✅ |
| Mục tiêu chính? | text | ✅ |
| User cuối là ai? | text | ❌ optional |
| Output mong muốn? | text | ❌ optional |

**Nhóm 2 — ML / DL Problem**

| Câu hỏi | Type | Required |
|---|---|---|
| Loại project? | select | ✅ |
| Đây là bài toán gì? | select | ✅ nếu ml/dl/rag |
| Input là gì? | select | ✅ nếu ml/dl/rag |
| Output là gì? | text | ✅ nếu ml/dl/rag |
| Dataset đã có chưa? | select | ✅ nếu ml/dl/rag |
| Dataset lớn khoảng bao nhiêu? | text | ❌ optional |
| Đã có label chưa? | confirm | ✅ nếu supervised |
| Có class imbalance không? | confirm | ❌ optional |

**Nhóm 3 — Evaluation**

| Câu hỏi | Type | Required |
|---|---|---|
| Metric chính là gì? | select + free text | ✅ |
| Có target score không? | text | ❌ optional |
| Có constraint về latency / cost? | text | ❌ optional |

**Nhóm 4 — Compute & Runtime**

| Câu hỏi | Type | Required |
|---|---|---|
| Có GPU không? | confirm | ✅ |
| Dùng môi trường nào? | select | ✅ nếu có GPU |
| Budget / deadline? | text | ❌ optional |
| Runtime (claude / codex / none)? | checkbox | ✅ |

**Output lưu vào:**

```
.octopus/project_state.json
.octopus/config.yaml           ← update last_updated
```

**Terminal output:**

```
🐙 Project state saved.

  Project: Vietnamese Emotion Classification
  Type:    text_classification
  Metric:  macro_f1
  Runtime: claude, codex

Run next:
  octopus plan
  octopus ml-plan
```

---

### 7.3. `octopus plan`

**Mục tiêu:** Sinh `requirements.md` từ project state.

**Usage:**

```bash
octopus plan
octopus plan --force    # Overwrite không hỏi
```

**Precondition:**

- `project_state.json` phải tồn tại.
- `project_name` và `project_type` không được rỗng.

**Logic:**

1. Load `ProjectState` từ JSON.
2. Nếu `requirements.md` đã tồn tại → backup thành `requirements.md.bak` và thông báo.
3. Render `requirements.md.j2` với state.
4. Ghi ra `requirements.md`.
5. In summary.

**Terminal output:**

```
📄 requirements.md generated.

  Backed up old file to: requirements.md.bak

Run next:
  octopus ml-plan    ← if this is an ML project
  octopus tasks
```

---

### 7.4. `octopus ml-plan`

**Mục tiêu:** Sinh kế hoạch ML/DL trước khi train.

**Usage:**

```bash
octopus ml-plan
octopus ml-plan --force
```

**Precondition:**

- `project_state.json` phải tồn tại.
- `project_type` phải là `ml`, `dl`, hoặc `rag`. Nếu không → print warning và exit.

**Logic:** Rule-based, không dùng LLM.

#### Rule map theo `task_type`

| `task_type` | `baseline_models` | `metrics` | `risks` |
|---|---|---|---|
| `text_classification` | TF-IDF + LR, TF-IDF + LinearSVC | macro F1, per-class recall, confusion matrix | class imbalance, noisy text, data leakage, overfitting |
| `image_classification` | Pretrained ResNet, MobileNet | accuracy, macro F1 if imbalanced | augmentation sai, train/val leakage, class imbalance |
| `regression` | Linear Regression, Random Forest, LightGBM | MAE, RMSE, R² | outlier, data leakage, target skew |
| `retrieval` / `rag` | BM25, dense embedding retrieval | Recall@k, MRR, nDCG | chunking kém, embedding không hợp domain, hallucination |
| `recommendation` | Popularity baseline, Matrix Factorization | Recall@k, NDCG@k, MRR | cold start, sparse interaction, time-based split sai |
| `forecasting` | Naive baseline, ARIMA, LightGBM | MAE, RMSE, MAPE | data leakage qua time, distribution shift, outlier |
| `clustering` | K-Means, DBSCAN | Silhouette Score, Davies-Bouldin | scale sensitivity, choosing k, noisy data |
| `anomaly_detection` | Isolation Forest, Autoencoder | Precision@k, Recall@k, AUC-PR | severe imbalance, threshold selection, false positive cost |

> Nếu `task_type` không nằm trong rule map → dùng default generic template, in cảnh báo: `⚠️ Task type not recognized. Generic template used.`

**Output:**

```
ml_design.md
experiment_plan.md
```

**Terminal output:**

```
📊 ml_design.md generated.
📋 experiment_plan.md generated.

  Task:     text_classification
  Baseline: TF-IDF + Logistic Regression
  Metric:   macro_f1
  Risks:    3 identified

Run next:
  octopus tasks
  octopus context --task "train TF-IDF baseline"
```

---

### 7.5. `octopus tasks`

**Mục tiêu:** Sinh task breakdown theo milestone.

**Usage:**

```bash
octopus tasks
octopus tasks --force
```

**Precondition:**

- `project_state.json` phải tồn tại.
- `task_type` không được rỗng nếu `project_type` là `ml/dl/rag`.

**Logic:**

1. Render `tasks.md.j2` với state (inject `baseline_models[0]`, `has_class_imbalance`...).
2. Baseline task (T010) luôn có trước main model task (T020) — enforce dependency.
3. Ghi ra `tasks.md`.

**Terminal output:**

```
✅ tasks.md generated.

  Milestones:  5
  Total tasks: 12
  Baseline enforced: Yes (T010 before T020)
```

---

### 7.6. `octopus context`

**Mục tiêu:** Tạo context file ngắn gọn cho Claude Code / Codex đọc.

**Usage:**

```bash
octopus context --task "train TF-IDF baseline"
octopus context inspect          # In ra terminal thay vì ghi file
```

**Precondition:**

- `project_state.json` phải tồn tại.
- Ít nhất một trong `requirements.md`, `ml_design.md`, `tasks.md` phải tồn tại.

**Phase 1 — Summarization strategy:**

> Phase 1 **không dùng LLM** để tóm tắt. Thay vào đó:
> - Include **toàn bộ nội dung** của các plan files (requirements, ml_design, experiment_plan, tasks).
> - Dùng `tiktoken` để estimate token count.
> - Nếu vượt ngưỡng `TOKEN_WARNING` → warn user.
> - Nếu vượt ngưỡng `TOKEN_HARD_LIMIT` → suggest dùng `--trim` flag (Phase 2).
>
> Lý do: Summarization bằng LLM đưa vào Phase 2 khi có memory layer.

**Token thresholds:**

```python
TOKEN_WARNING    = 8_000    # Yellow warning
TOKEN_HARD_LIMIT = 16_000   # Red warning + suggest trim
```

**Context file structure:**

```markdown
# Current Context — {{ project_name }}

> Generated: {{ generated_at }}
> Task: {{ task }}
> Estimated tokens: {{ estimated_tokens }}

---

## Current Task

{{ task }}

## Requirements Summary

{{ requirements_md_content }}

## ML Design Summary

{{ ml_design_md_content }}

## Experiment Plan

{{ experiment_plan_md_content }}

## Task List

{{ tasks_md_content }}

## Constraints

- Do not load raw datasets into context.
- Do not modify architecture without ADR.

## Expected Output

_Implement: {{ task }}_
```

**File exclusion — default rules:**

```
.venv/
__pycache__/
.git/
node_modules/
dist/ build/
*.pt *.pth *.ckpt *.onnx
*.pkl *.joblib
*.csv *.xlsx *.parquet *.jsonl
*.log
wandb/ mlruns/ checkpoints/
data/ datasets/
```

> Đọc thêm từ `.gitignore` nếu tồn tại, dùng `pathspec`.

**Output:**

```
.octopus/context/current_context.md
```

**Terminal output:**

```
📎 Context built.

  Task:    train TF-IDF baseline
  Output:  .octopus/context/current_context.md
  Tokens:  4,820 ✅ (within limit)

  Included:
    requirements.md
    ml_design.md
    experiment_plan.md
    tasks.md

  Excluded:
    data/ (gitignore)
    checkpoints/ (default rule)
    .venv/ (default rule)

Next step:
  Open Claude Code and say:
  "Follow the current Octopus context and implement the current task."
```

**Nếu vượt ngưỡng:**

```
⚠️  Token warning: 9,340 tokens (limit: 8,000)
    Consider splitting the task into smaller steps.
    Trim flag coming in Phase 2: octopus context --trim
```

---

### 7.7. `octopus sync`

**Mục tiêu:** Cập nhật `CLAUDE.md` và/hoặc `AGENTS.md` từ state hiện tại.

**Usage:**

```bash
octopus sync
octopus sync --runtime claude
octopus sync --runtime codex
```

**Precondition:**

- `project_state.json` phải tồn tại.
- `project_name` không được rỗng.

**Logic:**

1. Load state.
2. Nếu `runtime` có `claude` (hoặc `--runtime claude`) → render + ghi `CLAUDE.md`.
3. Nếu `runtime` có `codex` (hoặc `--runtime codex`) → render + ghi `AGENTS.md`.
4. Nếu cả hai → render cả hai.

**Terminal output:**

```
🔄 Synced.

  CLAUDE.md   ✅ updated
  AGENTS.md   ✅ updated
```

---

### 7.8. `octopus status` *(thêm mới)*

**Mục tiêu:** Hiện snapshot project — cho phép user kiểm tra nhanh trước khi chạy lệnh tiếp.

**Usage:**

```bash
octopus status
```

**Precondition:** Không có (luôn chạy được).

**Logic:**

- Nếu chưa `init` → print hướng dẫn `octopus init`.
- Nếu đã `init` nhưng chưa `ask` → print state rỗng + next step.
- Nếu có state đầy đủ → print bảng đẹp.

**Terminal output (đầy đủ):**

```
🐙 Octopus — Project Status

  Project   Vietnamese Emotion Classifier
  Type      text_classification
  Input     text → emotion_label
  Metric    macro_f1
  GPU       Yes (colab_t4)
  Runtime   claude, codex

  Files
  ✅ requirements.md       ✅ ml_design.md
  ✅ experiment_plan.md    ✅ tasks.md
  ✅ CLAUDE.md             ✅ AGENTS.md

  Context
  Last built: 2026-06-03 10:30
  Tokens:     4,820

  Next suggested command:
  octopus context --task "train TF-IDF baseline"
```

---

## 8. Precondition Guards

File `core/guards.py` — tập trung mọi precondition check.

```python
from pathlib import Path
from rich.console import Console
from octopus.core.paths import STATE_FILE, OCTOPUS_DIR, REQUIREMENTS_MD
import sys

console = Console()


def require_init():
    """Yêu cầu octopus init đã chạy."""
    if not OCTOPUS_DIR.exists():
        console.print("[red]❌ Octopus not initialized.[/red]")
        console.print("Run: [bold]octopus init[/bold]")
        sys.exit(1)


def require_state():
    """Yêu cầu project_state.json đã có."""
    require_init()
    if not STATE_FILE.exists():
        console.print("[red]❌ Project state not found.[/red]")
        console.print("Run: [bold]octopus ask[/bold]")
        sys.exit(1)


def require_ml_project():
    """Yêu cầu project_type là ml/dl/rag."""
    from octopus.storage.state_store import load_state
    state = load_state()
    if state.project_type not in ("ml", "dl", "rag"):
        console.print(f"[yellow]⚠️  ml-plan is only for ML/DL/RAG projects.[/yellow]")
        console.print(f"    Current type: {state.project_type}")
        sys.exit(0)


def require_plan_files():
    """Yêu cầu ít nhất 1 plan file tồn tại để build context."""
    require_state()
    plan_files = [REQUIREMENTS_MD, Path("ml_design.md"), Path("tasks.md")]
    if not any(f.exists() for f in plan_files):
        console.print("[red]❌ No plan files found.[/red]")
        console.print("Run: [bold]octopus plan[/bold] or [bold]octopus ml-plan[/bold] first.")
        sys.exit(1)
```

**Guard usage trong mỗi command:**

| Command | Guards cần gọi |
|---|---|
| `init` | Không cần |
| `ask` | `require_init()` |
| `plan` | `require_state()` |
| `ml-plan` | `require_state()`, `require_ml_project()` |
| `tasks` | `require_state()` |
| `context` | `require_state()`, `require_plan_files()` |
| `sync` | `require_state()` |
| `status` | Không cần (graceful fallback) |

---

## 9. Error Handling

### Nguyên tắc

- **User errors** (thiếu file, sai type) → in message rõ ràng bằng `Rich`, exit 0.
- **Unexpected errors** → in traceback rút gọn, exit 1.
- **File conflicts** → backup `.bak` trước khi overwrite, không xóa im lặng.

### Backup strategy

```python
def backup_if_exists(path: Path) -> Path | None:
    """Backup file bằng cách rename sang .bak. Return backup path hoặc None."""
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        path.rename(bak)
        return bak
    return None
```

### Atomic write

```python
import json, os
from pathlib import Path

def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
```

---

## 10. Token Management

File `context/token_estimator.py`:

```python
import tiktoken

ENCODING = "cl100k_base"   # Compatible với Claude và GPT-4
TOKEN_WARNING    = 8_000
TOKEN_HARD_LIMIT = 16_000


def estimate_tokens(text: str) -> int:
    enc = tiktoken.get_encoding(ENCODING)
    return len(enc.encode(text))


def get_token_status(token_count: int) -> str:
    if token_count >= TOKEN_HARD_LIMIT:
        return "exceeded"
    if token_count >= TOKEN_WARNING:
        return "warning"
    return "ok"


def format_token_display(token_count: int) -> str:
    status = get_token_status(token_count)
    if status == "exceeded":
        return f"[red]{token_count:,} ❌ (exceeded {TOKEN_HARD_LIMIT:,})[/red]"
    if status == "warning":
        return f"[yellow]{token_count:,} ⚠️  (approaching limit)[/yellow]"
    return f"[green]{token_count:,} ✅[/green]"
```

---

## 11. Test Plan

### `tests/conftest.py`

```python
import pytest
from pathlib import Path
import tempfile, os

@pytest.fixture
def tmp_project(tmp_path):
    """Tạo một project dir tạm thời và cd vào đó."""
    original = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original)
```

---

### `tests/test_init.py`

```python
def test_init_creates_all_files(tmp_project):
    """octopus init phải tạo đúng file/folder."""

def test_init_creates_claude_md_when_runtime_claude(tmp_project):
    """Nếu runtime có claude → tạo CLAUDE.md."""

def test_init_creates_agents_md_when_runtime_codex(tmp_project):
    """Nếu runtime có codex → tạo AGENTS.md."""

def test_init_does_not_overwrite_without_confirm(tmp_project):
    """Nếu .octopus/ đã tồn tại và user không confirm → không overwrite."""

def test_init_creates_octopus_subdirs(tmp_project):
    """Phải tạo: .octopus/context/, .octopus/experiments/, .octopus/adr/."""
```

---

### `tests/test_ml_plan.py`

```python
def test_ml_plan_text_classification_baseline(tmp_project):
    """text_classification → baseline phải có TF-IDF + LR."""

def test_ml_plan_text_classification_metrics(tmp_project):
    """text_classification → metrics phải có macro_f1."""

def test_ml_plan_regression_baseline(tmp_project):
    """regression → baseline phải có Linear Regression."""

def test_ml_plan_retrieval_baseline(tmp_project):
    """retrieval → baseline phải có BM25."""

def test_ml_plan_unknown_task_type_uses_generic(tmp_project):
    """task_type không có trong rule map → dùng generic template, không crash."""

def test_ml_plan_fails_for_software_project(tmp_project):
    """project_type = software → phải exit với warning, không generate file."""

def test_ml_plan_generates_both_files(tmp_project):
    """Phải sinh cả ml_design.md và experiment_plan.md."""
```

---

### `tests/test_context.py`

```python
def test_context_creates_output_file(tmp_project):
    """octopus context phải tạo .octopus/context/current_context.md."""

def test_context_excludes_venv(tmp_project):
    """.venv/ không được xuất hiện trong included_files."""

def test_context_excludes_data_dir(tmp_project):
    """data/ không được xuất hiện trong included_files."""

def test_context_excludes_checkpoint_files(tmp_project):
    """*.pt, *.pth, *.ckpt không được scan."""

def test_context_estimates_tokens_gt_zero(tmp_project):
    """estimated_tokens > 0 khi có ít nhất 1 plan file."""

def test_context_token_status_warning(tmp_project):
    """Context > 8000 tokens → token_status = 'warning'."""

def test_context_token_status_exceeded(tmp_project):
    """Context > 16000 tokens → token_status = 'exceeded'."""

def test_context_includes_task_name(tmp_project):
    """current_context.md phải chứa task name đã truyền vào."""
```

---

### `tests/test_guards.py`

```python
def test_require_init_fails_without_octopus_dir(tmp_project):
    """require_init() phải sys.exit(1) nếu .octopus/ chưa có."""

def test_require_state_fails_without_state_file(tmp_project):
    """require_state() phải sys.exit(1) nếu project_state.json chưa có."""

def test_require_ml_project_fails_for_software(tmp_project):
    """require_ml_project() phải exit nếu project_type = software."""
```

---

### `tests/test_token_estimator.py`

```python
def test_estimate_tokens_returns_int():
    """estimate_tokens() phải trả về int > 0 cho text bất kỳ."""

def test_token_status_ok_below_warning():
    """< 8000 tokens → status = 'ok'."""

def test_token_status_warning():
    """8000 <= tokens < 16000 → status = 'warning'."""

def test_token_status_exceeded():
    """tokens >= 16000 → status = 'exceeded'."""
```

---

## 12. Acceptance Criteria

Phase 1 được coi là xong khi toàn bộ các mục dưới đây được check:

### Setup

- [ ] Cài được package bằng `uv add` hoặc `pip install`
- [ ] Chạy được `octopus --help` và thấy danh sách 8 commands
- [ ] `ruff check .` không có lỗi
- [ ] `mypy` không có critical type error

### Commands

- [ ] `octopus init` tạo đúng cấu trúc file và thư mục
- [ ] `octopus init` không overwrite file cũ khi không confirm
- [ ] `octopus ask` lưu đúng `project_state.json`
- [ ] `octopus ask` lần 2 hoạt động ở merge mode (giữ giá trị cũ làm default)
- [ ] `octopus plan` sinh được `requirements.md` từ template
- [ ] `octopus plan` backup file cũ thành `.bak` trước khi overwrite
- [ ] `octopus ml-plan` sinh được `ml_design.md` và `experiment_plan.md`
- [ ] `octopus ml-plan` fail gracefully nếu project type không phải ML
- [ ] `octopus tasks` sinh được `tasks.md` với baseline task trước main model
- [ ] `octopus context --task "..."` sinh được `.octopus/context/current_context.md`
- [ ] `octopus context` không scan `.venv/`, `data/`, `checkpoints/`, file model
- [ ] `octopus context` in token estimate và status (ok / warning / exceeded)
- [ ] `octopus sync` cập nhật `CLAUDE.md` và/hoặc `AGENTS.md`
- [ ] `octopus status` hiển thị snapshot đúng kể cả khi chưa init

### Guards

- [ ] Mỗi command có precondition check đúng theo bảng guard
- [ ] Error message rõ ràng, hướng dẫn next step

### Tests

- [ ] Tất cả test case trong test plan pass
- [ ] Coverage ≥ 70% cho `core/`, `planners/`, `context/`

### Docs

- [ ] README có hướng dẫn cài đặt
- [ ] README có demo output của toàn bộ 8 commands

---

## 13. Demo cuối Phase 1

```bash
mkdir viet-emotion-classifier
cd viet-emotion-classifier

octopus init --runtime claude,codex
octopus ask
octopus plan
octopus ml-plan
octopus tasks
octopus context --task "train TF-IDF baseline"
octopus sync
octopus status
```

**Kết quả mong muốn:**

```
viet-emotion-classifier/
├── requirements.md
├── ml_design.md
├── experiment_plan.md
├── tasks.md
├── CLAUDE.md
├── AGENTS.md
│
└── .octopus/
    ├── config.yaml
    ├── project_state.json
    ├── context/
    │   └── current_context.md
    ├── experiments/
    └── adr/
```

**Sau đó user mở Claude Code và nói:**

```
Follow the current Octopus context and implement the current task.
```

Agent đọc `.octopus/context/current_context.md` thay vì user phải paste toàn bộ project context.

---

## 14. Scope không làm Phase 1

| Feature | Phase |
|---|---|
| MCP server | Phase 2 |
| Vector database / Semantic memory | Phase 2 |
| RAG-based context summarization | Phase 2 |
| Experiment history & query (SQLModel) | Phase 2 |
| MLflow / W&B connector | Phase 3 |
| GitHub / HuggingFace integration | Phase 3 |
| Auto training / AutoML | Phase 3 |
| Web dashboard | Phase 3 |
| Multi-agent orchestration | Phase 3 |
| `octopus context --trim` (LLM summarize) | Phase 2 |

---

## Kết luận Phase 1

Phase 1 chứng minh một điều duy nhất:

> **Octopus CLI giúp người dùng chuẩn bị project ML/DL rõ ràng trước khi code hoặc train, đồng thời tạo context đủ nhỏ để Claude Code / Codex làm việc hiệu quả — không cần paste thủ công.**

**Stack chốt:**

```
Python 3.11+ | uv | Typer | Rich | questionary
Pydantic v2 | Jinja2 | PyYAML | tiktoken | pathspec
pytest | ruff | mypy
```

**Commands chốt:**

```
octopus init      octopus ask      octopus plan
octopus ml-plan   octopus tasks    octopus context
octopus sync      octopus status
```