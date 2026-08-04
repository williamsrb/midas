# How to choose validation vs QA vs commit-message skills

**Scope:** `_shared`  
**Applies to:** Cursor delivery gates  
**Related:** [How-to-route-cursor-skills](../implementation/How-to-route-cursor-skills.md), [Quality-gate-delivery-standards.md](Quality-gate-delivery-standards.md)

## Prerequisites

- Know whether the need is requirements quality, syntax/lint, or commit text only.

## Procedure

1. Requirements / quality / security / less-code → `qa-validation` (review artifact: `qa-review` / `review-task`). Standards live under `~/.cursor/kb/validation/Quality-gate-*.md`.
2. Enonic backend JS syntax + commit message → `enonic-staged-validation-commit-message`.
3. Other stacks syntax + commit message → `generic-staged-validation-commit-message`.
4. Commit message only (no validate) → `staged-commit-message`.
5. Full merge of enonic+generic into one skill is **deferred** — keep dual skills until a later redesign phase.

## Shared quality-gate KB

| File | Purpose |
|------|---------|
| `Quality-gate-delivery-scope.md` | Staged → unstaged → branch diff resolution |
| `Quality-gate-delivery-standards.md` | Fix policy, fit, impact, quality, less-code, perf, security |
| `Quality-gate-response-template.md` | Chat QA report structure |

Reuse these from any skill that validates or drafts a delivery commit message — do not copy the rules inline.

## Pitfalls

- Do not run staged-validation expecting requirement-fit review — that is `qa-validation`.
- Do not skip `qa-validation` before staged-validation when the user asked for both quality and commit.
