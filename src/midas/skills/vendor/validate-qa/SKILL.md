---
name: validate-qa
aliases: qa-validation, review-task, validate-implementation
description: >-
  Validates the current solution delivery against requirements (fit, impact,
  quality, less-code, performance, security), applies targeted fixes, and can
  write a structured review artifact. Use for validate-qa, delivery QA, or
  task review. Before lint-and-draft-*-commit-message skills. Not for syntax-only
  passes or Bugbot/security subagents (escalate to those built-ins when needed).
---

# QA Validation

## Context budget (token)

1. Resolve `<TASK-ID>` via `../../kb/implementation/How-to-resolve-task-context.md`
2. Open **only** the allowlisted paths for this skill (see that How-to)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. Allowlist: delivery **diff** + `../../plans/<TASK-ID>.md` (AC / GO / validation block) when present. Do **not** read full PRD comments or the evidence plan by default

## Goal

Validate **and improve** the current solution delivery:

1. Confirm it fits requirements without breaking unrelated features.
2. Check code quality and less-code-is-better adherence.
3. Check for performance and security issues introduced by the delivery.
4. **Apply targeted source fixes** in the delivery scope to move closer to QA goals.

QA is not read-only (default mode). After analysis, edit code when a fix is safe, localized, and clearly improves QA metrics.

## Knowledge base (mandatory)

**Read and apply** these shared quality-gate guidelines before validating:

| Topic | Path |
|-------|------|
| Delivery scope (staged / unstaged / branch diff) | `../../kb/validation/Quality-gate-delivery-scope.md` |
| Standards (fix policy, fit, impact, quality, less-code, perf, security) | `../../kb/validation/Quality-gate-delivery-standards.md` |
| Chat report template | `../../kb/validation/Quality-gate-response-template.md` |

Other skills reusing delivery QA should read the same KB files instead of duplicating these rules.

## Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **qa** (default) | `validate-qa`, `delivery-qa`, `qa-check` | Full QA + fix loop; report in chat |
| **review** | `qa-review`, `review-task`, `implementation-review`, or user asks for a review file | Same checks + write `.tasks/<KEY>-review.md` (or `tasks/`); **less aggressive auto-fix** unless user asked to fix — see [references/review-mode.md](references/review-mode.md) |

If unclear, default to **qa**. Optional escalation: Bugbot / Security Review built-in skills (not this skill).

This skill runs entirely in the current agent session — no external Codex/CLI reviewer wrappers.

## Scope boundary

Do **not** duplicate work covered by follow-up skills `lint-and-draft-enonic-commit-message` or `lint-and-draft-generic-commit-message`:

- No commit message generation
- No full syntax/semantic pass (semicolons, brace balance, parse checks, unresolved imports) — those skills validate **and fix** those issues
- No Enonic XP CommonJS/ES5.1 rule pass — use the Enonic skill for that

You **may** fix obvious delivery bugs found during QA (undefined variables, broken braces, wrong format strings) when they block requirement fit or code quality.

Do **not** commit, push, or create PRs unless the user asks.

## Auxiliary skills (optional, on demand)

Not required for every run. When a QA/review step needs a specialized capability you cannot perform with already-installed skills / MCP / normal tools, and a session-only script is not worth it:

1. Prefer an already-installed skill if one covers the need (including Bugbot / Security Review when those are the right escalation).
2. Otherwise follow the `find-skills` skill as a nested prerequisite (`called_from: validate-qa`): search, verify quality, install if appropriate, then **read and follow** the new skill for the blocked action.
3. Resume this skill’s workflow after the gap is closed.

Example: validating against a design source requires a Figma reader that is not installed → `find-skills` → install/use it → continue QA.

## Workflow

Follow this sequence every time:

1. **Read KB** — `Quality-gate-delivery-scope.md`, `Quality-gate-delivery-standards.md`, `Quality-gate-response-template.md`.
2. **Resolve `<TASK-ID>`** — per `How-to-resolve-task-context.md`; assert branch matches before edits or STOP.
3. **Identify delivery scope** — per KB; state which tier (staged / unstaged / branch diff) is active.
4. **Restate the requirement** in one sentence — prefer `../../plans/<TASK-ID>.md` AC / validation block when the file exists; do not require the user to @-attach the PRD.
5. **Inspect the delivery diff** — read changed files and surrounding context as needed.
6. **Validate** — requirement fit, impact, code quality, less-code, performance, security (per KB standards).
7. **Optional — Impeccable (design / frontend UI only)** — **skip by default.** Only when the delivery clearly changes **design or frontend UI** (React/TSX views, CSS/styling, layout, visual components, UX copy on a surface). Skip for backend-only, API-only, schema-only, or non-UI diffs. When it applies: read the `impeccable` skill; optionally run `impeccable detect` on delivery UI paths (or `/impeccable audit|critique|polish` guidance). Treat findings as **Notes/Concerns** unless they clearly block the stated UI requirement; do not expand into a redesign the task did not ask for.
8. **Apply fixes** — per KB fix policy. In **review** mode, prefer reporting first; fix only clear Blockers unless the user asked to fix.
9. **Re-validate** — quick pass on the updated delivery diff.
10. **Output the QA report** — per KB response template.
11. **Review mode only** — follow [references/review-mode.md](references/review-mode.md) and write the review artifact when an issue key is known.
