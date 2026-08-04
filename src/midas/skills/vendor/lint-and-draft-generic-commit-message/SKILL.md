---
name: lint-and-draft-generic-commit-message
aliases: generic-staged-validation-commit-message, lint-and-suggest-generic-commit-msg, lint-generic-and-commit-msg-from-diff
description: Validates and fixes syntax/semantics and linter issues in the current solution delivery across languages/stacks, then drafts a commit message. Does not ask to commit or merge. Use for non–Enonic stacks or mixed non-XP deliveries. For Enonic XP / React4XP (backend JS and TS/TSX) use lint-and-draft-enonic-commit-message; for message-only use draft-commit-message; for requirements/quality review use validate-qa first.
---

# Generic Staged Validation + Commit Message

## Context budget (token)

1. Resolve `<TASK-ID>` from branch via `How-to-resolve-task-context.md` when needed for the message prefix
2. Read the delivery **diff only** (plus full file context for files in that diff)
3. Do **not** read `../../prds/` or `../../plans/` for this skill
4. Ignore extra @-attached harness MDs unless the user explicitly overrides

## Goal

Validate **and fix** the current solution delivery for syntax, semantics, and linter errors, then produce a commit message from the final delivery state.

For Enonic XP / React4XP deliveries, prefer `lint-and-draft-enonic-commit-message`.

## Knowledge base (mandatory)

| Topic | Path |
|-------|------|
| Delivery scope | `../../kb/validation/Quality-gate-delivery-scope.md` |

Do not copy that procedure into this skill.

## Workflow

1. **Identify delivery scope** — per KB; state tier.
2. **Inspect delivery diff** — hunks **and** full file context.
3. **Group files** by kind (source, tests, config, CI, docs) and note stack from repo cues.
4. **Syntax & semantic validation** — checks below per file type.
5. **Apply fixes** — blockers and safe issues (Fix policy).
6. **Re-validate** — until PASS or only unfixable blockers remain.
7. **Linter diagnostics** — `ReadLints` on touched sources after fixes.
8. **Optional tooling** — `tsc --noEmit`, `node --check`, etc. when quick and available.
9. **Commit message** — from **final** delivery diff; print full suggestion and stop.

Never run `git commit` or merge, and do not ask to commit or merge.

## Syntax & semantic validation (mandatory)

For **every source file** in the delivery, check and **fix**:

| Check | What to do |
|-------|------------|
| **Unclosed brackets** | Balance `{}`, `[]`, `()`; fix mismatches. |
| **Missing semicolons / statement termination** | Fix where required by style or ASI would break. |
| **Parse/syntax errors** | Language-appropriate checks (`node --check`, JSON.parse, YAML load); fix reported errors. |
| **Undefined / missing symbols** | Confirm calls, imports, identifiers resolve; fix typos/missing imports. |
| **Unresolved imports/requires** | Verify paths and exported names. |
| **Dangling references** | After renames/removals, grep leftovers. |
| **Dead or orphaned fragments** | Remove leftover lines from partial refactors. |

Read the **whole file** when the diff touches control flow, functions, or braces.

## Validation by file type

| Area | Guidance |
|------|----------|
| **JS / TS source** | Braces, semicolons, parse check, import/require resolution, undefined calls. |
| **Config / CI (JSON, YAML)** | Valid structure; fix trailing commas, bad indentation, broken keys. |
| **Typed languages** | Run `tsc`/compiler when project has it; fix errors in delivery scope. |
| **All text** | Secrets in diff, wrong paths, obvious dead code in changed hunks. |
| **Docs / markdown** | Broken links in changed sections; no fabricated changelog entries. |

## Fix policy

Apply fixes for syntax/semantic **Blockers**, clear local linter **errors**, and orphaned fragments introduced in the delivery.

Do **not** change behavior beyond the fix, refactor outside the delivery, or expand feature scope. Prefer the **smallest fix**. Re-validate after each pass.

## Linter checks

- `ReadLints` after fixes; fix clear local **errors**; summarize warnings.

## Commit message generation

Print **### Commit message suggestion**:

```text
[TASK-ID] Title of change
* Change 1
* Change 2
```

- `TASK-ID` = Jira key (or branch name if unknown) in **uppercase**.
- Title reflects **why** or **outcome**.

## Response template

```markdown
**Delivery scope:** staged | unstaged | branch diff vs main/master

### Fixes applied
- <file>: <what changed and why> — or "None"

### Syntax & semantic validation
- <path or group>: PASS | FAIL (<issue → fixed | remaining>)

### Linter
- <status summary after fixes>

### Commit message suggestion

    [TASK-ID] Title of change
    * Change 1
    * Change 2

```

Do not ask to commit or merge after the report.
