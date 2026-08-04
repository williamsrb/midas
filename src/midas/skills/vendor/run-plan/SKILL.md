---
name: run-plan
aliases: execute-plan, follow-plan, apply-plan, run-test-plan, run-implementation-plan, run-validation-plan
description: >-
  Executes an existing plan file while scanning the matching knowledge-base
  guideline folder for How-To hints, then writes reusable learnings back into
  the appropriate KB folder(s). When the user asks to run multiple plans at
  once (batch / parallel / several keys), route to multitask-same-repo instead.
  Use when the user asks to run, execute, follow, or apply a plan
  (implementation, evidence/testing, or validation/review).
disable-model-invocation: true
---

# Run Plan

Execute a plan file. Treat KB guidelines as **hints** (not a substitute for the plan). After the run, persist what you learned so future runs are faster.

## Context budget (token)

1. Resolve `<TASK-ID>` via `../../kb/implementation/How-to-resolve-task-context.md`
2. Open **only** the allowlisted paths for this skill (see that How-to)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. **Implementation run:** read `../../plans/<TASK-ID>.md` only (+ multitask `DECISIONS.md` / worktree `CLAUDE.md` if present). Do **not** read the full PRD unless the plan defers to a PRD section; do **not** read the evidence plan
7. **Evidence run:** read `../../plans/<TASK-ID>-evidence-plan.md` only. Do **not** read PRD or impl plan unless a step explicitly cites a path

## Multiple plans → multitask-same-repo

**Before** the single-plan workflow: if the user wants **two or more** plans run in the same request (batch, parallel, multitask, several issue keys / plan paths, “run these together”), **stop this skill** and **read and follow** `multitask-same-repo` instead (`called_from: run-plan`).

Triggers (any one is enough):

- Two or more distinct plan paths, or two or more issue keys each implying a plan
- Wording like batch / parallel / multitask / “all of these” / “these N plans”
- Same-repo multi-branch / multi-worktree implementation of several plans

Do **not** loop this skill once per plan in one session when the above applies — that reintroduces the fat-context failure mode. Hand off to `multitask-same-repo` for phase split, worktrees, and parallel fan-out; only use this skill for a **single** plan (or for one plan inside a fresh per-branch session that `multitask-same-repo` already scoped).

If it is unclear whether the user means one plan or many, ask once.

## Guideline roots

| Plan kind | Primary guideline folder (must follow / scan) | Typical plan cues |
|-----------|-----------------------------------------------|-------------------|
| **Implementation** | `../../kb/implementation` | `*.plan.md`, implementation todos, coding/build steps |
| **Testing / evidence** | `../../kb/testing` | `*evidence*`, test URLs, screenshots, QA evidence steps |
| **Validation / review** | `../../kb/validation` | validation, review, lint/QA gates, staged-validation |

Subfolders under a root (e.g. `testing/_shared/`, `testing/<project>/`) are part of that root — scan them when relevant.

**Follow primary; write anywhere:** Always **read/follow** the primary root for the plan kind. You **may write** learnings into **any** of the three roots when the knowledge belongs there (e.g. a testing run discovers an implementation tip → write under `implementation/`).

## Inputs

| Input | Required | Notes |
|-------|----------|--------|
| Plan path **or** `<TASK-ID>` | yes (exactly one plan) | Prefer convention paths under `../../plans`. User may pass only a key / “run implementation\|evidence for KEY” |
| Multiple plans | — | If two+ plans/keys: do not treat as this skill’s input set — route to `multitask-same-repo` |

### Resolve the single plan file

1. If the user gave an explicit path that exists, use it (legacy names only when explicitly pointed).
2. Else resolve `<TASK-ID>` via `How-to-resolve-task-context.md`, then:
   - Wording contains `evidence` / `test` → `../../plans/<TASK-ID>-evidence-plan.md`
   - Else → `../../plans/<TASK-ID>.md`
3. If that file is missing, ask once for the key or path — do **not** solicit PRD path or both plan types “just in case”.

Before code edits: assert `git branch --show-current` equals `<TASK-ID>` (or worktree folder matches) or STOP.

## Auxiliary skills (optional, on demand)

Not required for every run. When an execution step needs a specialized capability you cannot perform with already-installed skills / MCP / normal tools, and a session-only script is not worth it:

1. Prefer an already-installed skill if one covers the need (including skills the plan already names).
2. Otherwise follow the `find-skills` skill as a nested prerequisite (`called_from: run-plan`): search, verify quality, install if appropriate, then **read and follow** the new skill for the blocked action.
3. Resume this skill’s workflow (and KB write-back) after the gap is closed.

Example: the plan requires reading a Figma file and no reader is installed → `find-skills` → install/use it → continue the remaining todos.

Multi-plan orchestration is **not** optional auxiliary work — it is the gate at the top of this skill (`multitask-same-repo`).

## Workflow

```
- [ ] 0. Multi-plan gate → else continue
- [ ] 1. Load plan
- [ ] 2. Classify plan kind → primary guideline root
- [ ] 3. Scan primary guidelines (mandatory)
- [ ] 4. Execute plan steps
- [ ] 5. Write-back learnings (mandatory when new know-how was gained)
- [ ] 6. Report
```

### 0. Multi-plan gate

If multiple plans/keys are in scope (see **Multiple plans → multitask-same-repo**): hand off now. Do not load all plans into this session.

### 1. Load plan

Read the **one** allowlisted plan file fully. Note goals, acceptance criteria, todos/steps, blockers, and any explicit KB references already listed. Do **not** load PRD / the other plan kind / sibling tasks unless the plan body explicitly requires a cited path.

### 2. Classify plan kind

Pick **one primary** kind using filename + content (first strong match wins):

1. Name or title contains `evidence` / `test` / testing base URL / screenshot steps → **Testing**
2. Name or body centers on validation/review/lint/QA gate (not full evidence capture) → **Validation**
3. Otherwise (implementation todos, code changes, `.plan.md` coding work) → **Implementation**

If ambiguous, ask once; default to **Implementation**.

State in the run: `Plan kind: …` and `Primary KB: ../../kb/<root>`.

### 3. Scan primary guidelines (mandatory)

Before executing:

1. List How-To files under the primary root (recursive: `_shared/`, `<project>/`, top-level).
2. Read every guide that matches the plan’s work (auth, CMS, build, deploy, selectors, validation checks).
3. **Reuse** stable procedures/selectors/commands from those guides — do not rediscover blindly.
4. Note which files were used and any **gaps** to fill in step 5.

Project slug is usually the Jira project key lowercased (`GK` → `gk`) when a project subfolder exists.

### 4. Execute plan steps

- Follow the plan’s ordered steps/todos. Do not ask to switch modes.
- Honor plan warnings (auth, reachability, cross-scope frontend↔backend).
- If a specialized skill already covers a step (e.g. `validate-qa` for delivery QA), **follow that skill** for those steps instead of reinventing them — still apply this skill’s KB scan + write-back around the whole run.
- **Testing / evidence plans** (`*-evidence-plan.md`): follow the plan file’s own **Execution** section (E1–E3). Do **not** re-run `plan-task-evidence` for capture — that skill only writes the plan. Screenshots destined for Jira must pass consistency validation (correct element, zoom, example page) before upload — see `plan-task-evidence` reference / always-apply rule `jira-screenshot-consistency`; storage-only shots skip that gate.
- **Validation plans**: prefer `validate-qa` for delivery QA/review; use staged-validation skills for syntax+commit gates.
- On blockers: if the blocker is a missing specialized capability, try **Auxiliary skills** (`find-skills`) once before stopping. Otherwise stop, report, do not loop. Capture any partial learnings in step 5 if useful.

### 5. Write-back learnings

Run after execution (or after a useful partial run) whenever you gained reusable **how-to** knowledge.

**Store**

| Store in KB | Do **not** store |
|-------------|------------------|
| Repeatable procedure / checklist | Full screenshot sets, raw Jira comment dumps |
| Stable selectors, paths, commands, queries | Large datasets / every run’s IDs |
| Minimal sample data (one example) | Task-only prose already in the plan |
| Pitfalls, auth tips, “needs referer” notes | Secrets / credentials |

**Where to write**

- Prefer the **primary** root for learnings about that plan kind.
- Also write to **other** roots when the learning clearly belongs there (implementation tip found during testing → `implementation/`; validation check found during implement → `validation/`).
- Use `_shared/` for cross-project Enonic/CMS patterns; `<project>/` for app-specific flows when that layout exists. If the root is flat/empty, write `How-to-*.md` at the root or create `_shared/` / `<project>/` as needed.

**File rules**

- Name: `How-to-<verb>-<object>.md`
- Merge into an existing guide when the topic fits; split when mixing unrelated concerns.
- Format: same How-To shape as testing KB (title, Scope, Prerequisites, Procedure, Pitfalls, optional Sample data). For testing-shaped content, you may mirror [plan-task-evidence kb-format](../plan-task-evidence/kb-format.md).

Skip write-back only when every step was already fully covered by existing guides with no corrections.

### 6. Report

Return:

- Plan path + plan kind + primary KB root
- Outcome per major step (done / blocked / skipped)
- KB files **read**
- KB files **created/updated** (path + one-line why), including cross-root writes
- Manual follow-ups

## Examples

**Implementation plan:** user says `run I99X-341` or path `../../plans/I99X-341.md`  
→ resolve/read that file only; scan `../../kb/implementation`; execute coding todos.

**Evidence plan:** user says `run evidence I99X-341` or path `../../plans/I99X-341-evidence-plan.md`  
→ read evidence plan only; scan `../../kb/testing`; follow **Execution** (capture / Jira comment / KB write-back).

**Validation-oriented plan:** steps that are review/lint/gate focused  
→ scan `../../kb/validation`; record reusable checklists there.

**Multiple plans at once:** “run I99X-339, I99X-341, and I99X-343” or two+ plan paths  
→ do **not** execute here; read and follow `multitask-same-repo`.
