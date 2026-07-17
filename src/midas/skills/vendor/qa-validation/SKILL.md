---
name: qa-validation
description: Validates the current solution delivery against requirements, applies targeted source fixes to meet QA goals (requirement fit, impact safety, code quality, less-code-is-better), then reports results. Use when qa-validation is requested, before enonic-staged-validation-commit-message, or when reviewing whether a solution is complete and safe.
---

# QA Validation

## Goal

Validate **and improve** the current solution delivery:

1. Confirm it fits requirements without breaking unrelated features.
2. Check code quality and less-code-is-better adherence.
3. **Apply targeted source fixes** in the delivery scope to move closer to QA goals.

QA is not read-only. After analysis, edit code when a fix is safe, localized, and clearly improves QA metrics.

## Scope boundary

Do **not** duplicate work covered by follow-up skills `enonic-staged-validation-commit-message` or `generic-staged-validation-commit-message`:

- No commit message generation
- No full syntax/semantic pass (semicolons, brace balance, parse checks, unresolved imports) — those skills validate **and fix** those issues
- No Enonic XP CommonJS/ES5.1 rule pass — use the Enonic skill for that

You **may** fix obvious delivery bugs found during QA (undefined variables, broken braces, wrong format strings) when they block requirement fit or code quality.

Do **not** commit, push, or create PRs unless the user asks.

**Never run `git add` or `git restore --staged`.** Leave all agent edits unstaged; the user stages manually.

## Current solution delivery (target code)

All validation and fixes apply **only** to the current solution delivery. Resolve it in this order:

| Priority | Source | Git command |
|----------|--------|-------------|
| 1 | **Staged code** | `git diff --cached --name-only` and `git diff --cached` |
| 2 | **Unstaged changes** (when index is empty) | `git diff --name-only` and `git diff` |
| 3 | **Branch diff vs base** (when working tree is clean) | `git diff main...HEAD` or `git diff master...HEAD` (use whichever exists) |

Also run `git status --short` every time to confirm which case applies.

Rules:

- Prefer the **highest-priority** source that has content.
- When fixing, edit **only files in that delivery scope** unless a one-line import/caller fix is required to keep the delivery correct.
- After applying fixes, re-read the delivery diff to confirm improvements and no regressions.
- Do **not** stage fixes after editing — use `git diff` (unstaged) to verify.

## Workflow

Follow this sequence every time:

1. **Identify delivery scope** — run git commands above; state which tier (staged / unstaged / branch diff) is active.
2. **Restate the requirement** in one sentence (from user request or task context).
3. **Inspect the delivery diff** — read changed files and surrounding context as needed.
4. **Validate requirement fit** — every requirement part addressed? scope creep? dangling references?
5. **Assess impact on other features** — callers, routes, config, shared constants, exports.
6. **Review code quality** — correctness, conventions, redundant logic, obvious bugs.
7. **Review less-code-is-better** — see rules below; identify shrink/refactor opportunities **within the delivery**.
8. **Apply fixes** — edit source to address Blockers, Concerns, and clear less-code wins (see Fix policy).
9. **Re-validate** — quick pass on the updated delivery diff.
10. **Output the QA report** using the response template below.

## Fix policy

Apply fixes when they:

- Close a **Blocker** or **Concern** found during validation.
- Remove redundant code, dead branches, or single-use abstractions introduced in the delivery.
- Replace reinvented logic with an existing project function/module already used elsewhere.
- Fix obvious bugs (e.g. undefined variables, broken braces, wrong format strings) in the delivery.

Do **not** apply fixes when they:

- Expand scope beyond the stated requirement.
- Refactor unrelated files outside the delivery.
- Add new abstractions “for future reuse.”
- Require risky behavior changes without task context supporting them.

When unsure between **inline** vs **extract helper**: prefer **inline** unless the same logic appears **more than once in this delivery**.

## Requirement fit

Confirm:

- Every part of the stated requirement is addressed.
- Nothing beyond the requirement was added without justification.
- Deleted or renamed artifacts have no remaining references in the repo.
- Config, routes, and shared modules stay consistent with the change.

Flag gaps as **Blocker**, **Concern**, or **Note** — then fix Blockers and safe Concerns in code.

## Impact on other features

Check at least:

- Imports, requires, and exports still resolve.
- Site mappings, services, cron jobs, and tasks still align with remaining code.
- Config keys still make sense (empty vs removed vs repointed).
- Shared constants or utilities were not left partially dead.

State **PASS** only when unrelated features appear unaffected, or list concrete risks.

## Code quality

Review changed code for:

- Correctness and obvious logic errors
- Minimal, localized diff scope
- Consistency with surrounding project conventions (naming, patterns, module style)
- No redundant checks, wrappers, or abstractions
- No drive-by refactors unrelated to the task

Fix obvious quality issues in the delivery before reporting.

## Less-code-is-better

Prefer and reward:

- Smallest diff that fully solves the requirement
- Reuse of **existing** project functions instead of new helpers
- Deleting dead code instead of leaving unused exports or comments
- Inline logic over one-off abstractions

When improving the delivery, actively **reduce** changed line count when possible:

- Remove helpers used only once — inline them at the call site.
- Remove duplicate blocks — extract **only** if the same logic is used more than once **in this delivery**.
- Do not create reusable functions to be used only once; that is waste.
- **Future reusability is never the goal.** Focus on **present-time reusability**: if the same solution uses something more than once, then reusability is justified.

Flag and fix when the delivery adds unnecessary code, scope creep, or over-engineering.

## Response template

Use this structure:

```markdown
## QA validation

**Requirement:** <one-sentence restatement>

**Delivery scope:** staged | unstaged | branch diff vs main/master

**Verdict:** PASS | PASS WITH NOTES | FAIL

### Fixes applied
- <file>: <what changed and why> — or "None"

### Requirement fit
- <finding>

### Impact on other features
- <finding>

### Code quality
- <finding>

### Less-code-is-better
- <finding — include net diff impact if fixes reduced delivery size>

### Follow-up
- Run `enonic-staged-validation-commit-message` (Enonic backend JS) or `generic-staged-validation-commit-message` (other stacks) next — both validate **and fix** syntax/semantics/lint, then draft the commit message.
- <optional action items if FAIL or PASS WITH NOTES>
```

Rules:

- Be concise; bullets over long prose.
- Separate confirmed facts from assumptions.
- List every source edit under **Fixes applied** (file + brief reason).
- If validation is incomplete (e.g. missing runtime test), say so explicitly.
- If no fixes were needed, say `None` under **Fixes applied**.
- Re-run delivery diff commands after fixes so the report reflects final state.
