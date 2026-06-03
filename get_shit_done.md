# Phan tich repository Get Shit Done

## 1. Tom tat ngan

Repository nay chua he thong **GSD (Get Shit Done)**: mot framework meta-prompting, context engineering va spec-driven development cho cac AI coding runtime nhu Claude Code, Codex, Gemini CLI, OpenCode, Kilo, Copilot, Cursor, Windsurf, Augment, Trae, Qwen, Hermes, CodeBuddy va Cline.

No khong phai mot web app hay backend service truyen thong. No la mot bo **CLI + SDK + command/skill + workflow + agent + hook** duoc cai vao AI coding tools de dieu phoi qua trinh phat trien phan mem bang AI.

Trang thai can luu y:

- `README.md` o root noi repository nay da khong con la home active cua GSD; project tiep tuc o `open-gsd/gsd-core`.
- Tuy vay checkout hien tai van la mot package npm day du voi version `1.50.0-canary.0`.
- Phan tich duoi day dua tren code va tai lieu dang co trong repo nay.

## 2. Repo nay dang lam gi?

GSD cung cap mot quy trinh co cau truc de bien y tuong thanh code thong qua AI agents:

1. Khoi tao project bang hoi dap, research, requirements va roadmap.
2. Chia roadmap thanh cac phase co artifact ro rang.
3. Thao luan tung phase de lay context va quyet dinh.
4. Research cach thuc implement phase.
5. Lap PLAN.md chi tiet.
6. Kiem tra plan bang agent rieng.
7. Execute plan bang executor agents, co commit atomic.
8. Verify ket qua theo goal cua phase.
9. Lam UAT, review UI, security audit, code review, ship PR.
10. Luu memory vao `.planning/` de tiep tuc sau context reset.

No giai quyet van de lon cua AI coding la **context rot** va **workflow drift**. Thay vi de AI chat tu do trong mot context dai dan, GSD bat moi buoc sinh ra artifact doc duoc, de agent sau co the doc dung thong tin can thiet.

## 3. Cong nghe chinh

### Node.js package root

Root package la `get-shit-done-cc`, yeu cau Node.js `>=22`.

Thanh phan chinh:

- `bin/install.js`: installer chinh cua package.
- `bin/gsd-sdk.js`: shim goi `sdk/dist/cli.js`.
- `get-shit-done/bin/gsd-tools.cjs`: CLI legacy/compatibility.
- `get-shit-done/bin/lib/*.cjs`: cac module CommonJS domain logic.
- `commands/gsd/*.md`: command/skill source.
- `agents/gsd-*.md`: agent role definitions.
- `hooks/*`: runtime hooks.
- `scripts/*`: build, lint, release, scan, generator scripts.

Root JavaScript dung CommonJS, style hai space indentation, semicolon, `node:` imports cho built-ins o cac vung moi.

### SDK TypeScript

`sdk/` la package rieng `@gsd-build/sdk`, TypeScript ESM voi `NodeNext`.

SDK cung cap:

- `GSD`: public class de chay plan, phase, milestone.
- `GSDTools`: bridge cho state/config/roadmap/query.
- `createRegistry()`: query registry typed.
- `gsd-sdk query`: CLI query layer moi.
- `PhaseRunner`, `InitRunner`, `ContextEngine`, `PromptFactory`.
- event stream va transport CLI/WebSocket.

Huong moi cua repo la dua workflow sang SDK query registry, con `gsd-tools.cjs` duoc giu de tuong thich nguoc.

### Tests

Repo co hai he test:

- Root tests: `node:test` trong `tests/*.test.cjs`, chay qua `scripts/run-tests.cjs`.
- SDK tests: Vitest trong `sdk/src/*.test.ts` va integration tests.

Commands quan trong:

```bash
npm test
npm run test:coverage
npm run build:hooks
npm run build:sdk
cd sdk && npm test
cd sdk && npm run build
```

## 4. Cau truc thu muc

### `commands/gsd/`

Chua user-facing command definitions. Moi file la markdown co YAML frontmatter va body prompt.

Vi du:

- `new-project.md`
- `discuss-phase.md`
- `plan-phase.md`
- `execute-phase.md`
- `verify-work.md`
- `code-review.md`
- `debug.md`
- `ship.md`

Repo hien co 67 command theo inventory hien tai. Sau v1.40 co them 6 namespace meta-skills:

- `gsd-workflow`
- `gsd-project`
- `gsd-quality`
- `gsd-context`
- `gsd-manage`
- `gsd-ideate`

Muc dich cua meta-skill la giam token cost: model thay 6 router ngan thay vi mot danh sach command rat dai.

### `get-shit-done/workflows/`

Chua workflow markdown. Workflow la orchestration logic: doc context, goi SDK/CLI, spawn agents, update state.

Repo hien co 88 workflow markdown o root cua thu muc nay.

Workflow quan trong:

- `new-project.md`
- `discuss-phase.md`
- `plan-phase.md`
- `execute-phase.md`
- `execute-plan.md`
- `verify-phase.md`
- `verify-work.md`
- `transition.md`
- `autonomous.md`
- `quick.md`
- `debug.md`
- `map-codebase.md`
- `code-review.md`
- `sync-skills.md`

### `agents/`

Chua agent role files. Moi agent co frontmatter ve ten, description, tool permissions, mau hien thi, va body huong dan.

Repo hien co 33 GSD agents, gom cac nhom:

- Researcher: `gsd-project-researcher`, `gsd-phase-researcher`, `gsd-ui-researcher`, `gsd-ai-researcher`, `gsd-domain-researcher`.
- Planner: `gsd-planner`, `gsd-roadmapper`, `gsd-eval-planner`.
- Executor: `gsd-executor`.
- Checker/verifier: `gsd-plan-checker`, `gsd-verifier`, `gsd-integration-checker`, `gsd-ui-checker`, `gsd-nyquist-auditor`.
- Reviewer/fixer: `gsd-code-reviewer`, `gsd-code-fixer`, `gsd-security-auditor`, `gsd-ui-auditor`.
- Docs/intel/profile/debug: `gsd-doc-writer`, `gsd-doc-verifier`, `gsd-doc-classifier`, `gsd-doc-synthesizer`, `gsd-intel-updater`, `gsd-user-profiler`, `gsd-debugger`, `gsd-debug-session-manager`.

### `get-shit-done/references/`

Shared knowledge cho workflow va agents. Day la "standard library" ve cach GSD nghi va hanh dong.

Vi du:

- `model-profiles.md`
- `model-profile-resolution.md`
- `planning-config.md`
- `agent-contracts.md`
- `gates.md`
- `checkpoints.md`
- `verification-patterns.md`
- `git-integration.md`
- `context-budget.md`
- `planner-gap-closure.md`
- `planner-reviews.md`
- `thinking-models-*.md`

### `get-shit-done/templates/`

Chua template artifact duoc tao trong `.planning/`:

- `project.md`
- `requirements.md`
- `roadmap.md`
- `state.md`
- `phase-prompt.md`
- `summary.md`
- `verification-report.md`
- `UI-SPEC.md`
- `UAT.md`
- `VALIDATION.md`
- `DEBUG.md`
- `research-project/*`
- `codebase/*`

### `get-shit-done/bin/lib/`

Day la domain layer CJS cua CLI legacy va compatibility.

Module quan trong:

- `core.cjs`: output, error, shared helpers, config defaults projection.
- `planning-workspace.cjs`: `.planning/` root, workstream routing, locks.
- `state.cjs`: parse/update `STATE.md`.
- `roadmap.cjs`: parse/update `ROADMAP.md`.
- `phase.cjs`: phase dirs, phase numbering, plan index.
- `config.cjs`: `.planning/config.json`.
- `verify.cjs`: plan/phase/reference/commit validation.
- `template.cjs`: fill templates.
- `frontmatter.cjs`: frontmatter CRUD.
- `init.cjs`: compound context loading cho workflows.
- `workstream.cjs`: parallel workstreams.
- `model-profiles.cjs` va `model-catalog.cjs`: model/tier resolution.
- `runtime-homes.cjs`: mapping runtime -> config dir.
- `runtime-artifact-layout.cjs`: mapping runtime -> command/skill/agent artifact layout.
- `shell-command-projection.cjs`: portable shell/hook command generation.
- `security.cjs`: safe path, prompt injection, shell arg validation.
- `cjs-sdk-bridge.cjs`: bridge tu CJS sang SDK registry.
- `command-routing-hub.cjs`: huong moi de gom dispatch policy cho command families.

### `hooks/`

Hooks tich hop vao AI runtime:

- `gsd-statusline.js`: hien model, state, cwd, context usage.
- `gsd-context-monitor.js`: canh bao context con lai.
- `gsd-check-update.js` va worker: update check.
- `gsd-prompt-guard.js`: scan `.planning/` writes cho prompt injection.
- `gsd-read-injection-scanner.js`: scan output doc doc vao.
- `gsd-workflow-guard.js`: advisory guard cho edit ngoai workflow.
- `gsd-read-guard.js`: read-before-edit guard.
- `gsd-session-state.sh`: session tracking.
- `gsd-validate-commit.sh`: commit validation.
- `gsd-phase-boundary.sh`: phase transition detection.

## 5. Kien truc tong the

Kien truc co the hinh dung nhu sau:

```text
User
  |
  | /gsd-command hoac $gsd-command
  v
Command/Skill layer
  commands/gsd/*.md
  |
  v
Workflow layer
  get-shit-done/workflows/*.md
  |
  | gsd-sdk query / gsd-tools.cjs
  | spawn specialized agents
  v
Agent layer
  agents/gsd-*.md
  |
  v
SDK/CLI tools layer
  sdk/src/query/*
  get-shit-done/bin/lib/*
  |
  v
File state layer
  .planning/PROJECT.md
  .planning/REQUIREMENTS.md
  .planning/ROADMAP.md
  .planning/STATE.md
  .planning/config.json
  .planning/phases/*
```

Nguyen tac cot loi:

- Orchestrator mong, agent chuyen mon sau.
- Moi agent co fresh context window.
- State la file markdown/json, khong dung database.
- Artifact tao ra phai doc duoc boi human va AI.
- Verify la buoc rieng, khong de executor tu cham diem minh.
- Config absent = enabled voi nhieu workflow toggle.
- SDK registry la duong moi; CJS CLI la duong compatibility.

## 6. Luong chay chinh

### 6.1 New project flow

```text
User idea / PRD
  -> /gsd-new-project
  -> adaptive questions hoac --auto @file.md
  -> project researchers chay song song
  -> synthesize research
  -> tao REQUIREMENTS.md
  -> tao ROADMAP.md
  -> tao STATE.md va config.json
  -> user approve roadmap
```

Artifact sinh ra:

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/config.json`
- `.planning/research/SUMMARY.md`
- `.planning/research/STACK.md`
- `.planning/research/FEATURES.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`

### 6.2 Phase planning flow

```text
/gsd-discuss-phase N
  -> tao CONTEXT.md

/gsd-ui-phase N neu la frontend
  -> tao UI-SPEC.md

/gsd-plan-phase N
  -> init context qua gsd-sdk query
  -> phase research neu can
  -> tao RESEARCH.md
  -> spawn planner
  -> tao PLAN.md files
  -> spawn plan-checker
  -> iterate toi khi pass hoac cham max loop
  -> update STATE.md
```

Plan phase co nhieu gate:

- research gate
- package legitimacy gate
- plan checker loop
- requirements coverage gate
- decision coverage gate
- optional plan bounce
- optional TDD/MVP mode

### 6.3 Execute phase flow

```text
/gsd-execute-phase N
  -> doc plan index
  -> phan tich dependency
  -> gom plans thanh waves
  -> spawn executor agents theo wave
  -> moi executor implement mot PLAN.md
  -> commit atomic
  -> tao SUMMARY.md
  -> verifier kiem tra phase goal
  -> tao VERIFICATION.md
  -> transition state neu pass
```

Execution co wave model:

- plans khong phu thuoc nhau co the chay song song.
- wave sau doi wave truoc.
- co co che worktree va commit safety.
- state write dung lock de tranh race.

### 6.4 Verify/UAT/ship flow

```text
/gsd-verify-work N
  -> conversational UAT
  -> tao hoac update UAT.md
  -> gap neu co thi route ve diagnose/fix/plan gaps

/gsd-code-review hoac /gsd-ui-review
  -> audit source/UI

/gsd-ship
  -> prepare PR, review, merge readiness
```

## 7. `.planning/` la memory layer

Trong project su dung GSD, `.planning/` la trung tam state.

File cot loi:

- `PROJECT.md`: vision, constraints, technical decisions.
- `REQUIREMENTS.md`: requirement IDs va scope.
- `ROADMAP.md`: phases, status, requirement mapping.
- `STATE.md`: current position, phase, status, decisions, blockers, metrics.
- `config.json`: settings, workflow toggles, model profile, git strategy, hooks.

Phase artifacts thuong gap:

- `{phase}-CONTEXT.md`
- `{phase}-RESEARCH.md`
- `{phase}-{plan}-PLAN.md`
- `{phase}-{plan}-SUMMARY.md`
- `{phase}-VERIFICATION.md`
- `{phase}-UAT.md`
- `{phase}-UI-SPEC.md`
- `{phase}-VALIDATION.md`

Vi state la file:

- AI co the doc truc tiep.
- Human co the review va commit vao git.
- Context reset khong lam mat trang thai.
- Workflow co the resume bang `.planning/STATE.md` va artifact lien quan.

## 8. Runtime va cach cai dat

Installer `bin/install.js` la thanh phan bien source repo thanh artifact cho runtime.

Runtime spelling khac nhau:

- Claude Code / OpenCode / Kilo / Copilot: `/gsd-command-name`
- Gemini CLI: `/gsd:command-name`
- Codex: `$gsd-command-name`
- Mot so runtime dung skill directory thay vi slash command directory.

Installer phai lam nhieu viec:

- copy command/skill files.
- convert namespace hyphen/colon tuy runtime.
- convert tool names giua Claude/Copilot/Codex-style tools.
- install agent definitions.
- install hooks.
- ghi settings/config cua runtime.
- chon install profile: full/core/minimal/custom profile.
- migration install cu.
- sync surface giua cac runtime.

`runtime-homes.cjs` mapping runtime sang config dir, vi du:

- `claude` -> `~/.claude`
- `codex` -> `~/.codex`
- `gemini` -> `~/.gemini`
- `opencode` -> `~/.config/opencode`
- `kilo` -> `~/.config/kilo`
- `grok` -> `~/.agents`

Luu y ve Grok Build:

- `docs/discussions/grok-build-support-2026-05.md` la active discussion hien tai.
- `runtime-homes.cjs` da co `grok`.
- `runtime-artifact-layout.cjs` van ghi ro `grok` co y chua duoc wire vao layout table.
- Vi vay Grok hien nen duoc hieu la partial/local compatibility direction, chua la first-class installer path hoan chinh trong module layout.

## 9. SDK vs CJS CLI

### CJS CLI legacy

`get-shit-done/bin/gsd-tools.cjs` tap trung nhieu command:

- state
- roadmap
- phase
- config
- verify
- template fill
- frontmatter
- milestone
- workstream
- docs
- learnings
- graphify
- import tu GSD-2

No la compatibility implementation cho workflow cu va shell scripts.

### SDK query registry

`sdk/src/query/` la huong canonical moi.

No co:

- registry assembly
- command aliases
- query dispatch
- mutation event decorator
- fallback policy
- typed error taxonomy
- handlers cho state, roadmap, phase, verify, config, init, workspace, workstream, decisions, intel, docs, skills.

`gsd-sdk query ...` dung longest-prefix command resolution. Neu handler chua co trong SDK, co the fallback sang CJS tuy policy.

Y nghia kien truc:

- Workflow moi nen goi `gsd-sdk query`.
- CJS tiep tuc song de tranh break install/runtime cu.
- Tests lock parity giua CJS va SDK.

## 10. Model profiles va agent routing

GSD khong hardcode mot model duy nhat cho moi viec. No co layer model profiles:

- `quality`
- `balanced`
- `budget`
- `adaptive`
- `inherit`

Config co the set:

- `model_profile`
- `model_overrides`
- `models.<phase_type>`
- `dynamic_routing`
- runtime-aware tier mapping

Agent categories duoc map sang tier nhu opus/sonnet/haiku hoac runtime-native model ID. Runtime co the co `reasoning_effort`.

Muc tieu:

- Planner/research/verifier co the dung model manh hon.
- Executor hoac task don gian co the dung model re hon.
- Dynamic routing co the escalate khi that bai.

## 11. Quality gates va safety

Repo co nhieu lop phong ve:

- Plan checker verify plan truoc execution.
- Verifier verify sau execution.
- UAT verify voi human.
- UI checker/auditor cho frontend.
- Security auditor va security enforcement.
- Prompt injection scanners.
- Read-before-edit guard.
- Workflow guard.
- Commit validation.
- Schema drift detection.
- Package legitimacy gate bang slopcheck.
- Fallow structural review optional.
- Secret/base64/prompt-injection scan scripts.

Day la mot diem quan trong: GSD khong chi "prompt AI code"; no co nhieu gate de lam workflow bot ngau hung thanh workflow co audit trail.

## 12. Workstreams, workspaces va parallelization

Repo ho tro nhieu cach lam viec song song:

- `workstreams`: nhieu stream `.planning/workstreams/<name>/`.
- `workspace`: tao isolated workspace bang worktree/clone.
- execution waves: song song trong cung phase neu plans doc lap.
- worktree safety: quan ly git worktrees, prune, health inspect.
- active workstream store: route command vao workstream hien tai.

Config lien quan:

- `parallelization.enabled`
- `parallelization.max_concurrent_agents`
- `workflow.use_worktrees`
- `workflow.worktree_skip_hooks`
- `planning.sub_repos`

## 13. Codebase intelligence

GSD co cac workflow/doc cho brownfield projects:

- `/gsd-map-codebase`: spawn codebase mapper agents.
- `/gsd-graphify`: build/query knowledge graph.
- `/gsd-extract-learnings`: rut bai hoc tu phase da xong.
- `intel`: queryable codebase knowledge files.
- `docs-update`: update docs co verification.
- `ingest-docs`: classify/synthesize ADR/PRD/SPEC/DOC de bootstrap `.planning/`.

Artifact lien quan:

- `.planning/codebase/stack.md`
- `.planning/codebase/architecture.md`
- `.planning/codebase/structure.md`
- `.planning/codebase/testing.md`
- `.planning/codebase/integrations.md`
- `.planning/codebase/concerns.md`
- `.planning/intel/*.json`

## 14. Configuration

Config project nam o `.planning/config.json`.

Nhom config quan trong:

- `mode`: interactive/yolo.
- `granularity`: coarse/standard/fine.
- `model_profile`: quality/balanced/budget/adaptive/inherit.
- `workflow`: research, plan_check, verifier, auto_advance, ui_phase, node_repair, tdd_mode, use_worktrees, code_review, security_enforcement.
- `parallelization`: concurrency control.
- `git`: branch templates, tag creation.
- `gates`: confirm gates.
- `safety`: destructive/external confirmation.
- `review`: default reviewers va external CLI commands.
- `hooks`: context warnings, workflow guard.
- `agent_skills`: inject skills vao agent types.
- `features`: thinking partner, global learnings.
- `intel`: queryable codebase intelligence.

Pattern quan trong: nhieu workflow toggle dung **absent = enabled**. Neu key thieu, mac dinh la bat.

## 15. Cach repo ap dung vao thuc te

### Khi dung trong project moi

User cai GSD vao runtime, sau do trong repo can lam:

```text
/gsd-new-project
/gsd-progress
/gsd-discuss-phase 1
/gsd-plan-phase 1
/gsd-execute-phase 1
/gsd-verify-work 1
/gsd-ship
```

Sau moi buoc, GSD ghi artifact vao `.planning/`. Neu session AI bi reset, lenh `/gsd-resume-work` hoac `/gsd-progress` doc lai artifact de tiep tuc.

### Khi dung trong codebase co san

Flow thuong la:

```text
/gsd-map-codebase
/gsd-ingest-docs
/gsd-new-project --auto @existing-prd.md
/gsd-plan-phase N --ingest docs/adr/xxxx.md
```

GSD dung codebase map, ADR, docs, decisions de lap plan phu hop voi he thong dang co.

### Khi can sua nhanh

Co cac duong ngan:

- `/gsd-fast`: task rat nho, inline.
- `/gsd-quick`: task nhanh nhung van co GSD guarantees.
- `/gsd-debug`: debug co state.
- `/gsd-code-review --fix`: review va auto-fix.
- `/gsd-audit-fix`: audit-to-fix pipeline.

### Khi lam voi nhieu AI runtime

Repo co install/sync logic de cung mot source surface co the deploy sang nhieu runtime. Day la ly do co nhieu code ve:

- namespace conversion
- runtime homes
- artifact layout
- skill profiles
- hook projection
- command aliases
- Grok/Codex/Gemini/Claude compatibility

## 16. Nhung diem dang phat trien/nhay cam

### Repo redirect

Root README noi repo da move sang `open-gsd/gsd-core`. Neu lam feature moi cho upstream, can kiem tra repo moi.

### SDK migration

Repo dang o giai do chuyen tu CJS `gsd-tools.cjs` sang SDK query registry. Vi vay co nhieu module bridge/parity/generator.

### Multi-runtime complexity

So runtime nhieu lam installer phuc tap. Moi runtime co:

- path rieng.
- skill/command layout rieng.
- command namespace rieng.
- hook format rieng.
- agent/tool permission model rieng.

### Grok Build

Tai lieu discussion thang 05/2026 noi Grok Build compatibility la active topic. Trang thai trong code cho thay:

- Co mapping home cho `grok`.
- Co discussion ve `~/.agents` layout.
- Chua co layout artifact first-class trong `runtime-artifact-layout.cjs`.

Vi vay khong nen xem Grok la fully completed neu chi doc code hien tai.

## 17. Ket luan

Repo nay la mot he sinh thai automation cho AI-assisted software delivery. Kien truc cua no gom:

- npm installer de cai vao AI runtime.
- markdown commands lam user-facing surface.
- markdown workflows lam orchestrators.
- specialized agent definitions.
- `.planning/` lam file-based state database.
- CJS CLI compatibility layer.
- TypeScript SDK/query registry lam huong moi.
- hooks de tang safety va UX.
- tests rat rong de giu parity, runtime compatibility va regression safety.

Gia tri cot loi cua GSD la ep AI coding vao mot quy trinh co traceability: moi quyet dinh, requirement, plan, execution summary, verification va UAT deu thanh artifact co the doc, commit, review va resume.
