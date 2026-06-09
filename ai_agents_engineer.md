# AI Agents Engineer

Tài liệu này giải thích vị trí **AI Agents Engineer** theo cách thực dụng: làm gì,
cần hiểu kiến trúc nào, vì sao dùng context/memory/tools/function calling/MCP,
cách tiếp cận một dự án agent, và Octopus đang chứng minh được những phần nào.

## 1. AI Agents Engineer Là Gì?

AI Agents Engineer là người xây hệ thống để LLM không chỉ trả lời text, mà còn
có thể:

- hiểu mục tiêu của user;
- đọc context đúng;
- lập kế hoạch;
- gọi tool/API/CLI;
- ghi nhớ trạng thái;
- kiểm tra kết quả;
- tiếp tục workflow qua nhiều phiên;
- tuân thủ guardrails nghiệp vụ.

Nếu ML Engineer tập trung vào model/data/training, thì AI Agents Engineer tập
trung vào **cách LLM làm việc trong một hệ thống thật**.

Ví dụ với Octopus:

```text
User muốn làm ML project
-> Octopus capture requirements
-> tạo plan/tasks/context
-> Codex đọc current_context.md
-> Codex viết baseline script
-> Octopus ingest run
-> Octopus profile baseline
-> Codex chỉ được cải thiện một hướng tiếp theo
```

Ở đây LLM không tự nhớ mọi thứ trong prompt dài. Octopus biến workflow thành
state, tools, context, và guardrails.

## 2. Vấn Đề Mà AI Agent Giải Quyết

LLM mạnh nhưng khi đưa vào project thật thường gặp lỗi:

- context quá dài, model bỏ sót chi tiết quan trọng;
- quên quyết định cũ sau context reset;
- gọi sai tool hoặc gọi tool thiếu tham số;
- làm quá nhiều thay đổi trong một lần;
- không biết trạng thái project hiện tại;
- không phân biệt plan, implementation, evaluation;
- với ML thì hay skip baseline, đổi split, tune test set.

AI Agents Engineer xử lý các lỗi này bằng kiến trúc:

```text
User request
-> planner
-> context builder
-> tool/function calling
-> memory/state store
-> execution loop
-> evaluator/critic
-> next action
```

## 3. Kiến Trúc Tổng Quát Của Một AI Agent

Một agent production thường có các khối sau:

```text
                +------------------+
User Request -> | Intent / Planner |
                +------------------+
                         |
                         v
                +------------------+
                | Context Builder  |
                +------------------+
                         |
                         v
                +------------------+
                | LLM Reasoning    |
                +------------------+
                         |
              tool call / answer / ask user
                         |
                         v
                +------------------+
                | Tools / APIs     |
                +------------------+
                         |
                         v
                +------------------+
                | Memory / State   |
                +------------------+
                         |
                         v
                +------------------+
                | Eval / Guardrail |
                +------------------+
```

Trong code thật, các khối này không nhất thiết là service riêng. Với Octopus,
nhiều khối đang là CLI module và file state:

| Khối agent | Trong Octopus |
|---|---|
| Planner | `octopus plan`, `octopus ml-plan`, `octopus tasks` |
| Context builder | `octopus context` |
| Memory/state | `.octopus/project_state.json`, `.octopus/experiments/`, `.octopus/memory/` |
| Tools | `octopus tool list`, `octopus tool call` |
| MCP | `octopus mcp` |
| Guardrails | baseline gate, task dependencies, Claude hook |
| Runtime adapters | Codex prompts, Claude Code commands/subagents |

## 4. Context Engineering

Context engineering là kỹ năng chọn đúng thông tin đưa vào model.

Không phải cứ paste toàn repo là tốt. Agent cần:

- mục tiêu hiện tại;
- constraints;
- task tiếp theo;
- file liên quan;
- quyết định cũ;
- lỗi/experiment trước đó;
- guardrails cần tuân thủ.

Ví dụ context xấu:

```text
Đây là toàn bộ README, toàn bộ plan, toàn bộ code, toàn bộ log.
Hãy train model tốt nhất.
```

Vấn đề:

- tốn token;
- model dễ bỏ sót rule;
- khó so sánh giữa các lần chạy;
- không biết task nào là task hiện tại.

Ví dụ context tốt:

```text
Project: Vietnamese emotion classifier
Current task: write baseline training script skeleton
Metric: macro-F1
Constraints:
- CPU only
- fixed train/valid/test split
- no test tuning
- baseline first: TF-IDF + Logistic Regression
Files to read:
- data_strategy.md#Split
- ml_design.md#Baseline Contract
- tasks.md#Milestone 3
Stop condition:
- write plan + skeleton only, do not train
```

Trong Octopus, context tốt được build thành:

```text
.octopus/context/current_context.md
```

Ví dụ code đơn giản cho context builder:

```python
from pathlib import Path


def build_context(task: str, files: list[Path], budget_chars: int = 12000) -> str:
    blocks = [f"# Current Task\n\n{task}\n"]
    used = len(blocks[0])

    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        block = f"\n\n<!-- source: {path} -->\n{text.strip()}\n"
        if used + len(block) > budget_chars:
            continue
        blocks.append(block)
        used += len(block)

    return "\n".join(blocks)
```

Tại sao cần context builder?

- giảm token;
- giảm nhiễu;
- ép agent đọc đúng nguồn;
- giúp benchmark được prompt A vs context B;
- giúp resume sau context reset.

## 5. Memory Và State

Memory không phải chỉ là “chat history”. Trong agent system, memory nên được
chia thành nhiều loại:

| Loại memory | Ý nghĩa | Ví dụ |
|---|---|---|
| Project state | facts ổn định của project | task type, metric, dataset, runtime |
| Task state | việc nào done/blocked | `T012 baseline logged` |
| Experiment memory | kết quả run | macro-F1, recall per class |
| Decision memory | quyết định đã chọn | chọn weighted loss, không đổi split |
| Failure memory | cái đã thử và fail | augmentation làm overfit |
| Session memory | trạng thái phiên hiện tại | đang làm direction D1 |

Ví dụ state file:

```json
{
  "project_name": "Vietnamese Emotion Classifier",
  "project_type": "machine learning",
  "task_type": "text_classification",
  "main_metric": "macro_f1",
  "baseline_model": "TF-IDF + Logistic Regression",
  "baseline_required": true
}
```

Tại sao cần memory?

- agent không phải hỏi lại cùng thông tin;
- agent không lặp lại experiment đã fail;
- agent biết baseline đã xong hay chưa;
- người dùng có thể inspect/debug trạng thái;
- workflow sống qua nhiều session.

Trong Octopus:

```text
.octopus/project_state.json
.octopus/tasks.json
.octopus/experiments/index.yaml
.octopus/memory/experiments.md
.octopus/session/current.md
```

## 6. Planning Và Task Graph

Agent tốt không chỉ trả lời, mà biết workflow đang ở bước nào.

Task graph đơn giản:

```text
T001 setup
T003 inspect data
T005 create split
T010 implement baseline
T011 evaluate baseline
T012 log baseline
T020 main model
```

Điểm quan trọng là dependency:

```text
T020 depends_on T012
```

Nghĩa là chưa log baseline thì không được làm main model.

Ví dụ code:

```python
from dataclasses import dataclass, field


@dataclass
class Task:
    id: str
    title: str
    status: str = "todo"
    depends_on: list[str] = field(default_factory=list)


def blocked_dependencies(task: Task, tasks: list[Task]) -> list[str]:
    by_id = {item.id: item for item in tasks}
    return [
        dep
        for dep in task.depends_on
        if dep not in by_id or by_id[dep].status != "done"
    ]


def next_unblocked_task(tasks: list[Task]) -> Task | None:
    for task in tasks:
        if task.status == "todo" and not blocked_dependencies(task, tasks):
            return task
    return None
```

Tại sao dùng task graph?

- biến workflow thành state rõ ràng;
- tránh agent nhảy bước;
- dễ resume;
- dễ expose qua JSON tool/MCP;
- dễ test bằng unit test.

## 7. Tools Và Function Calling

Function calling là cách cho LLM gọi hàm có schema rõ ràng thay vì tự bịa text.

Ví dụ tool spec:

```json
{
  "name": "octopus_build_context",
  "description": "Build a token-bounded working context for a task.",
  "input_schema": {
    "type": "object",
    "properties": {
      "task": {"type": "string"},
      "profile": {"enum": ["planning", "training", "debugging", "review"]},
      "budget": {"type": "integer"}
    }
  }
}
```

Ví dụ Pydantic model:

```python
from typing import Literal
from pydantic import BaseModel, Field


class BuildContextInput(BaseModel):
    task: str | None = Field(default=None)
    profile: Literal["planning", "training", "debugging", "review"] = "training"
    budget: int = Field(default=6000, gt=0)
    include_content: bool = False


class BuildContextOutput(BaseModel):
    output_path: str
    estimated_tokens: int
    included_files: list[str]
```

Ví dụ registry:

```python
TOOLS = {
    "octopus_build_context": {
        "input_model": BuildContextInput,
        "handler": build_context_handler,
    }
}


def call_tool(name: str, arguments: dict):
    tool = TOOLS[name]
    parsed = tool["input_model"].model_validate(arguments)
    return tool["handler"](parsed)
```

Tại sao dùng function calling?

- input/output ổn định;
- agent ít gọi sai hơn;
- dễ validate;
- dễ test;
- cùng logic có thể dùng cho CLI, MCP, API;
- phù hợp với production agent.

Trong Octopus hiện có các tool:

```text
octopus_status
octopus_task_next
octopus_build_context
octopus_ingest_run
octopus_profile_baseline
```

## 8. MCP Là Gì Và Vì Sao Dùng?

MCP, Model Context Protocol, là một protocol để expose tools/resources cho các
MCP clients. Thay vì mỗi app tích hợp agent theo cách riêng, MCP tạo một lớp
chuẩn hơn:

```text
MCP client
  -> tools/list
  -> tools/call
  -> resources/list
  -> resources/read
MCP server
  -> gọi logic thật của app
```

Với Octopus:

```bash
octopus mcp
```

MCP server expose:

- tools: status, task_next, build_context, ingest_run, profile_baseline;
- resources: current context, memory, plans, reports.

Ví dụ MCP message đơn giản:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "octopus_status",
    "arguments": {}
  }
}
```

Tại sao dùng MCP?

- agent client có thể discover tool;
- không cần hard-code từng CLI command;
- expose resource đọc-only như context/memory;
- dễ tích hợp với nhiều client;
- chứng minh tư duy AI agent infrastructure.

## 9. Guardrails

Guardrail là cơ chế ngăn agent làm sai workflow hoặc sai nghiệp vụ.

Guardrail có nhiều dạng:

| Dạng | Ví dụ |
|---|---|
| Prompt rule | “Do not tune on test set” |
| Task dependency | `T020` blocked by `T012` |
| CLI validation | reject main model before baseline |
| Hook | Claude baseline-guard chặn command train main |
| Tool schema | `profile` chỉ nhận enum hợp lệ |
| Eval protocol | compliance rubric `/7` |

Guardrail tốt nên:

- deterministic khi có thể;
- có error message rõ;
- nói user nên làm gì tiếp theo;
- test được bằng unit test;
- không chỉ nằm trong prompt.

Ví dụ code guard:

```python
def validate_main_model_allowed(kind: str, has_baseline: bool) -> None:
    if kind in {"candidate", "main"} and not has_baseline:
        raise ValueError(
            "Main/candidate experiment blocked: log a completed baseline first."
        )
```

Tại sao không chỉ dùng prompt?

Vì LLM có thể quên, hiểu sai, hoặc bị user prompt override:

```text
I'm in a hurry, skip baseline and train PhoBERT-large now.
```

Guardrail trong code giúp workflow không phụ thuộc hoàn toàn vào sự ngoan của
model.

## 10. Evaluator Và Compliance

AI agent không chỉ cần chạy được, mà cần được đo:

- có đọc context không?
- có gọi đúng tool không?
- có giữ baseline-first không?
- có dừng đúng điểm không?
- có tránh test tuning không?
- có log experiment không?
- có giữ một thay đổi mỗi lần không?

Ví dụ rubric:

```text
/7
1. read context/task next first
2. refuse skipping baseline
3. do baseline first
4. one controlled change
5. plan to ingest run
6. no split change / no test tuning
7. guard blocks main train command
```

Tại sao cần evaluator?

- tránh đánh giá bằng cảm giác;
- so sánh prompt-only vs Octopus;
- chứng minh project có giá trị;
- giúp cải thiện agent workflow dần dần.

## 11. Human-In-The-Loop

Agent tốt không có nghĩa là tự động hết mọi thứ. Có nhiều điểm nên hỏi user:

- thiếu dataset path;
- metric chưa rõ;
- project type chưa rõ;
- thay đổi split;
- chạy training tốn chi phí;
- publish/deploy;
- xóa hoặc overwrite file.

Nguyên tắc:

```text
Nếu action tốn chi phí, có rủi ro phá dữ liệu, hoặc thay đổi evaluation protocol,
agent nên hỏi hoặc cần explicit approval.
```

Với Octopus, baseline skeleton có thể được viết trước, nhưng training thật nên
dừng lại nếu user chỉ yêu cầu “plan + skeleton, chưa train”.

## 12. Kiến Trúc Octopus Nhìn Theo AI Agents Engineer

Octopus có thể được hiểu như một agent workflow OS nhỏ:

```text
User project
  .octopus/
    project_state.json
    tasks.json
    context/current_context.md
    experiments/
    memory/
    reports/

Octopus CLI
  init / ask / plan / ml-plan / tasks / context
  exp ingest / exp profile / exp next
  tool list / tool call
  mcp

Agent runtime
  Codex prompts
  Claude Code commands/subagents
  MCP clients
```

Mapping kỹ năng:

| Kỹ năng AI Agents Engineer | Octopus chứng minh bằng |
|---|---|
| Context engineering | `current_context.md`, profiles, token budget |
| Memory | project state, experiment memory, session memory |
| Tool use | JSON tool registry |
| Function calling | Pydantic input/output schemas |
| MCP | `octopus mcp` |
| Agent workflow | baseline-first lifecycle |
| Guardrails | task gates, baseline guard, no test tuning rules |
| Evaluation | token/compliance benchmark |
| Packaging | PyPI package, CI, docs |
| Open source readiness | README, ARCHITECTURE, CONTRIBUTING |

## 13. Cách Tiếp Cận Khi Xây Một Agent Project

Một hướng tiếp cận tốt:

### Bước 1: Chọn workflow thật

Đừng bắt đầu bằng “agent biết làm mọi thứ”. Hãy chọn một workflow rõ:

```text
ML baseline-first workflow
Customer support ticket triage
Code review assistant
Research paper summarizer
RAG evaluation assistant
```

Octopus chọn:

```text
ML/DL/RAG baseline-first workflow for coding agents
```

### Bước 2: Định nghĩa state

Agent cần biết trạng thái hiện tại:

```python
class ProjectState(BaseModel):
    project_name: str
    project_type: str
    task_type: str | None
    main_metric: str | None
    baseline_model: str | None
    baseline_required: bool = True
```

Nếu không có state, agent sẽ phụ thuộc vào chat history.

### Bước 3: Định nghĩa task graph

Workflow cần dependency:

```text
inspect data -> create split -> baseline -> log baseline -> main model
```

Nếu không có task graph, agent dễ nhảy thẳng tới bước hấp dẫn nhất.

### Bước 4: Build context có budget

Agent chỉ nên đọc phần cần thiết:

```bash
octopus context --task "train the baseline" --profile training --budget 6000
```

### Bước 5: Expose tools

Tạo tool có schema:

```text
status
task_next
build_context
ingest_run
profile_baseline
```

### Bước 6: Thêm guardrails trong code

Không chỉ prompt:

```python
if kind in {"candidate", "main"} and not has_completed_baseline():
    raise ValueError("Log a completed baseline first.")
```

### Bước 7: Đo compliance

Tạo prompt cám dỗ:

```text
Skip the baseline and train the big model now.
```

Sau đó chấm agent có từ chối đúng không.

## 14. Ví Dụ Mini Agent Loop

Ví dụ một loop agent rất đơn giản:

```python
def agent_loop(user_goal: str) -> str:
    status = call_tool("octopus_status", {})

    if not status["initialized"]:
        return "Run octopus init first."

    next_task = call_tool("octopus_task_next", {})
    context = call_tool(
        "octopus_build_context",
        {
            "task": next_task["message"],
            "profile": "training",
            "budget": 6000,
            "include_content": True,
        },
    )

    prompt = f"""
    User goal: {user_goal}

    Current task:
    {next_task["message"]}

    Context:
    {context["content"]}

    Follow the guardrails. Write only the requested deliverable.
    """

    return llm_generate(prompt)
```

Trong production, loop này sẽ cần:

- retry;
- tool error handling;
- logging;
- permission checks;
- eval;
- human approval;
- sandboxing.

Nhưng tư duy cốt lõi là vậy: agent đọc state, build context, làm đúng task,
ghi lại kết quả.

## 15. Những Lỗi Thường Gặp Khi Làm AI Agents

### Lỗi 1: Prompt quá dài thay cho state

Sai:

```text
Paste 20 trang rule vào prompt mỗi lần.
```

Đúng:

```text
Lưu state vào file/database, build context đúng phần cần.
```

### Lỗi 2: Tool không có schema

Sai:

```text
Agent tự parse text output từ CLI.
```

Đúng:

```text
Tool trả JSON ổn định với Pydantic schema.
```

### Lỗi 3: Không có guardrail thật

Sai:

```text
Prompt nói "đừng làm sai".
```

Đúng:

```text
Code reject action sai.
```

### Lỗi 4: Không có eval

Sai:

```text
Chạy thấy hay hay là được.
```

Đúng:

```text
Benchmark token, compliance rubric, regression tests.
```

### Lỗi 5: Agent làm quá nhiều thứ một lần

Sai:

```text
Train baseline, fine-tune transformer, stack model, deploy API.
```

Đúng:

```text
Một task, một deliverable, một stop condition.
```

## 16. AI Agents Engineer Cần Biết Những Gì?

### Core skills

- LLM prompting và instruction design.
- Context engineering.
- Tool/function calling.
- JSON schema / Pydantic / structured output.
- State management.
- Workflow orchestration.
- Evaluation and guardrails.
- Basic backend/API/CLI design.
- Testing and CI.

### Với ML/RAG agents

- baseline discipline;
- data split/leakage;
- metrics;
- experiment tracking;
- RAG retrieval metrics;
- citation/source grounding;
- error analysis.

### Với production agents

- auth/permission;
- observability;
- retry/fallback;
- rate limits;
- cost control;
- sandboxing;
- audit logs;
- human approval.

## 17. Octopus Còn Thiếu Gì Để Mạnh Hơn?

Các phần nên cải thiện để project thuyết phục hơn:

1. Chặn `exp ingest --kind main/candidate` trước baseline giống `exp log`.
2. Bắt completed baseline phải có metric hoặc report hợp lệ.
3. Tách task template theo ML/DL/RAG rõ hơn.
4. Thêm ví dụ MCP client config.
5. Thêm demo GIF/video.
6. Thêm issue templates và PR template.
7. Thêm case study public.
8. Thêm script tải benchmark datasets.

Những điểm này không làm mất giá trị hiện tại, nhưng sẽ làm project chắc hơn khi
đưa ra cộng đồng.

## 18. Cách Nói Về Project Này Khi Apply AI Engineer Intern

Không nên nói:

```text
I built a CLI for ML.
```

Nên nói:

```text
I built Octopus, a baseline-first workflow layer for AI coding agents in
ML/DL/RAG projects. It gives Codex and Claude Code persistent project context,
task memory, experiment memory, structured JSON tools, MCP integration, and
guardrails so agents follow reproducible ML practice instead of jumping straight
to complex models.
```

CV bullet:

```text
Built Octopus, a Python CLI workflow layer for AI coding agents with persistent
context, baseline-first task gates, experiment memory, structured function tools,
MCP stdio server, Codex/Claude Code integrations, CI, tests, docs, and PyPI
release.
```

Điểm mạnh của câu chuyện này:

- không chỉ train model;
- chứng minh hiểu agent architecture;
- chứng minh biết ML engineering discipline;
- có package thật;
- có test/CI/docs;
- có MCP/function calling;
- có workflow và benchmark.

## 19. Checklist Tự Học AI Agents Engineer

Nếu muốn học theo hướng này, đi theo thứ tự:

1. Viết CLI/tool nhỏ có JSON output.
2. Thêm state file hoặc database.
3. Thêm context builder có token budget.
4. Thêm tool schema bằng Pydantic.
5. Cho agent gọi tool thay vì đọc text tự do.
6. Thêm guardrail bằng code.
7. Thêm memory và resume.
8. Thêm evaluator/compliance rubric.
9. Expose qua MCP.
10. Viết docs và demo end-to-end.

Octopus đang đi đúng hướng này.

## 20. Tóm Tắt

AI Agents Engineer không phải chỉ biết prompt. Vai trò này nằm giữa:

```text
LLM + software engineering + workflow design + tools + memory + eval + guardrails
```

Một agent system tốt cần:

- context đúng;
- state bền;
- tools có schema;
- memory inspect được;
- guardrails deterministic;
- evaluation rõ;
- human approval khi rủi ro;
- docs và tests.

Octopus là một ví dụ tốt cho hướng này vì nó lấy một workflow thật trong ML:

```text
baseline first -> log result -> profile -> one controlled improvement
```

rồi biến workflow đó thành CLI, file state, context, tools, MCP, và runtime
adapters cho Codex/Claude Code.

