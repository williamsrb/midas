# How to resolve task context (TOKEN)

**Scope:** `_shared` harness — plan / implement / QA / evidence pipeline  
**Applies to:** Cursor and Claude Code skills that touch Jira task artifacts  
**Related:** `How-to-optimize-agent-token-usage.md`, `How-to-route-cursor-skills.md`

## Canonical paths

| Artifact | Path (skill-relative) | Absolute |
|----------|----------------------|----------|
| PRD | `../../prds/<TASK-ID>.md` | `~/.cursor/prds/<TASK-ID>.md` |
| Implementation plan | `../../plans/<TASK-ID>.md` | `~/.cursor/plans/<TASK-ID>.md` |
| Evidence / test plan | `../../plans/<TASK-ID>-evidence-plan.md` | `~/.cursor/plans/<TASK-ID>-evidence-plan.md` |
| Git branch | exactly `<TASK-ID>` | — |
| Multitask worktree | `<multitask-root>/<TASK-ID>/` | folder name = `<TASK-ID>` |
| Shared decisions | `<multitask-root>/DECISIONS.md` | when multitask |

Do **not** invent alternate plan names (e.g. `*.plan.md`) for new work. Open a legacy filename only when the user explicitly points at it.

## Resolve `<TASK-ID>`

Stop at the first hit:

1. Explicit key or Jira URL in the user message (`[A-Z][A-Z0-9]+-\d+`)
2. `git branch --show-current` if it matches that pattern
3. CWD / workspace folder name if it matches (multitask worktree)
4. Else ask once for the key — **never** ask for full paths to PRD / impl plan / evidence plan when the convention files exist

After resolve:

- Before code edits (implement / QA / lint): assert `git branch --show-current` equals `<TASK-ID>` or STOP
- Multitask: code lives under `<root>/<TASK-ID>/`; harness MD stays under `../../prds` and `../../plans`

## Context budget (every pipeline skill)

1. Resolve `<TASK-ID>` with this How-to
2. Open **only** the allowlisted paths for the active skill (table below)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. Never paste full MD bodies into the user-visible prompt; Read/Grep the files

## Per-step read allowlist

| Step | Skill(s) | Must read | Must **not** read by default |
|------|----------|-----------|------------------------------|
| Download | `download-jira-task` | Jira MCP → write PRD only | Other tasks' PRDs/plans |
| Draft impl plan | `plan-implementation` | PRD: `## Description` + AC-bearing sections first; `## Comments` only if AC incomplete | Full comments when Description already has AC; evidence plan; sibling PRDs; whole offline-reference catalogs (use llm-index) |
| Validate/fix plan | `plan-implementation` validate mode / `multitask-same-repo` Phase 1 | Draft `plans/<TASK-ID>.md` + sectioned PRD | Evidence plan; delivery diff; other keys' full plans |
| Run impl | `run-plan` | **`plans/<TASK-ID>.md` only**; `DECISIONS.md` if multitask; worktree `CLAUDE.md` if present | Full PRD unless plan says see PRD §…; evidence plan; other worktrees |
| QA gate | `validate-qa` | Delivery **diff** + `plans/<TASK-ID>.md` (AC / GO / validation block) | Full PRD comments; evidence plan |
| Lint + commit msg | `lint-and-draft-*` / `draft-commit-message` | Delivery diff only; TASK-ID from branch | `prds/`; `plans/` |
| Draft evidence plan | `plan-task-evidence` | AC from `plans/<TASK-ID>.md` first; PRD sectioned only for tips/URLs/comment ids when plan lacks them | Full impl narrative; full PRD comments; siblings |
| Validate evidence plan | `plan-task-evidence` | `plans/<TASK-ID>-evidence-plan.md` + AC source used in draft | Full impl plan; full PRD |
| Run evidence | `run-plan` / `run-test-plan` | **`plans/<TASK-ID>-evidence-plan.md` only** | PRD; impl plan unless a step cites a path |
| Jira comment | Evidence Execution (E2) | Evidence outcomes + templates in skill `templates.md` | Re-read PRD/impl plan to "summarize the whole task" |

## `run-plan` path resolution

If the user gives only `<TASK-ID>` or "run implementation/evidence":

- Wording contains `evidence` / `test` → `../../plans/<TASK-ID>-evidence-plan.md`
- Else → `../../plans/<TASK-ID>.md`

Stop asking for an absolute plan path when that file exists.
