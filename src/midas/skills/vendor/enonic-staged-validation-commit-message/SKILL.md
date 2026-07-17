---
name: enonic-staged-validation-commit-message
description: Validates and fixes the current solution delivery for Enonic XP 7.16 backend JavaScript (CommonJS, syntax/semantics, linter issues), drafts a commit message, then optionally asks to commit and merge into a validation branch (review/staging/qa/test). Use when Enonic XP backend/CommonJS validation is requested or when preparing a commit message.
---

# Enonic Staged Validation + Commit Message

## Goal

Validate **and fix** the current solution delivery for Enonic XP backend JavaScript, then produce a commit message from the final delivery state.

This skill is not read-only. Find syntax/semantic issues **and apply fixes** before reporting.

## Scope

Apply backend Enonic XP rules only when all match:

- The request is for Enonic XP backend validation.
- Files are **backend** JavaScript for Enonic XP (controllers, services, libs under `xp/`), not React4XP/React/Next.js code.

Never apply Enonic backend rules to:

- TypeScript: `*.ts`, `*.tsx`
- React4XP code (entries, components, build output)
- Next.js projects or files
- Frontend/browser JS (bundles, client utilities, `assets/js/`)
- Generated/bundled frontend assets

For frontend JS in the delivery, run **generic syntax/semantic checks** (see below) but skip Enonic CommonJS/ES5.1 rules.

Do **not** commit, push, merge, or create PRs during validation (steps 1–9). Optional **Steps 10–11** below ask the user before any git write.

**Never run `git add` or `git restore --staged`.** Leave all agent edits unstaged; the user stages manually.

## Current solution delivery (target code)

Resolve delivery scope in this order:

| Priority | Source | Git command |
|----------|--------|-------------|
| 1 | **Staged code** | `git diff --cached --name-only` and `git diff --cached` |
| 2 | **Unstaged changes** (when index is empty) | `git diff --name-only` and `git diff` |
| 3 | **Branch diff vs base** (when working tree is clean) | `git diff main...HEAD` or `git diff master...HEAD` |

Also run `git status --short` every time.

Rules:

- Prefer the **highest-priority** source that has content.
- Validate and fix **only files in that delivery scope**.
- After fixes, re-run diff commands and re-validate until clean or remaining issues are reported as blockers.
- Do **not** stage fixes after editing — use `git diff` (unstaged) to verify.

## Workflow

Follow this sequence every time:

1. **Identify delivery scope** — git commands above; state tier (staged / unstaged / branch diff).
2. **Inspect delivery diff** — read changed hunks **and full file context** around edits (errors often sit outside the diff hunk).
3. **Classify files** — backend Enonic JS vs frontend/other; apply the matching rule set per file.
4. **Syntax & semantic validation** — run checks below; record every issue.
5. **Apply fixes** — fix blockers and safe issues in delivery scope (see Fix policy).
6. **Re-validate** — repeat steps 4–5 until PASS or only unfixable blockers remain.
7. **Linter diagnostics** — `ReadLints` on touched source files after fixes.
8. **Optional tooling** — when available, run quick syntax checks (e.g. `node --check <file>` for backend JS).
9. **Commit message** — draft from **final** delivery diff; **include the full suggestion in your response** (see Response template) before any git prompt.
10. **Optional: run git commit** — ask only **after** Step 9 is visible to the user (see [Optional git steps](#optional-git-steps)).
11. **Optional: merge into validation branch** — ask only if Step 10 was approved and the commit succeeded.

## Syntax & semantic validation (mandatory)

For **every source file** in the delivery, check and **fix**:

| Check | What to do |
|-------|------------|
| **Unclosed brackets** | Balance `{}`, `[]`, `()`; fix mismatched or dangling braces from bad merges/edits. |
| **Missing semicolons / statement termination** | Fix where required by project style or where omission breaks ASI (e.g. before `(`, `[`, `` ` `` on next line). |
| **Parse/syntax errors** | Run `node --check` on changed `.js` backend files when Node is available; fix reported errors. |
| **Undefined / missing functions** | For each call in changed code, confirm the symbol is defined in-file, exported from a `require()` target, or a known global; fix wrong names or add missing `require`. |
| **Unresolved requires** | Confirm `require('...')` paths resolve to existing modules in the project; fix paths or exports. |
| **Dangling references** | After renames/removals in the delivery, grep for leftover symbol/route/config references. |
| **Dead or orphaned fragments** | Remove leftover lines from partial refactors (e.g. references to removed variables like `candidates`). |

Read the **whole file** when the diff touches control flow, functions, or braces — not only changed lines.

## Backend JS validation rules (Enonic XP 7.16)

For each backend JS file in the delivery:

- CommonJS only (`require`, `exports`, `module.exports`); no ESM `import`/`export`.
- Syntax: ES5.1 + allowed extras:
  - arrow functions
  - template strings (not containing regex patterns)
  - `let` and `const`
  - default parameters
  - computed property names
  - object shorthand
- Flag and **fix** unsupported modern syntax (e.g. `async`/`await`, spread in unsupported contexts, optional chaining) when a safe ES5.1-compatible rewrite exists within the delivery.

If no backend JS files are in the delivery, state that and skip Enonic-specific rules.

## Fix policy

Apply fixes when they:

- Fix syntax/semantic **Blockers** (unclosed braces, parse errors, undefined calls, broken requires).
- Resolve linter **errors** (not warnings) in delivery files.
- Correct Enonic CommonJS/ES5.1 violations with a minimal local rewrite.

Do **not** apply fixes when they:

- Change behavior beyond what is needed to fix the error.
- Refactor unrelated code outside the delivery.
- Expand feature scope.

Prefer the **smallest fix** that makes the file valid. Inline over new helpers unless the same logic is duplicated in the delivery.

After each fix pass, re-read the file and re-run validation checks.

## Linter checks

- Run `ReadLints` on all touched source files **after** fixes.
- Fix linter **errors** in the delivery when the fix is clear and local.
- Report warnings; fix only when trivial and in changed code.
- If diagnostics look stale, re-read the file and note the risk.

## Commit message generation

Use **final delivery diff** (after fixes). Do not execute the commit until optional Step 10 is approved.

**Presentation order (mandatory):** In the same response as validation results, output the
**### Commit message suggestion** block with the complete message (title + bullets) **before**
calling `AskQuestion` or asking whether to commit. The user must see the exact message that
would be used if they approve Step 10.

Required format:

```text
[BRANCH] Title of change
- Change 1
- Change 2
```

Rules:

- `BRANCH` = current git branch name in uppercase.
- Title reflects why/outcome.
- Bullets summarize meaningful deltas (include fix-only changes if they were part of this delivery).

## Response template

```markdown
**Delivery scope:** staged | unstaged | branch diff vs main/master

### Fixes applied
- <file>: <what changed and why> — or "None"

### Syntax & semantic validation
- <file>: PASS | FAIL (<issue → fixed | remaining>)

### Enonic backend JS (XP 7.16)
- <file>: PASS | FAIL | SKIPPED (<reason>)

### Linter
- <status summary after fixes>

### Commit message suggestion

    [BRANCH] Title of change
    - Change 1
    - Change 2

### Optional git (if user approved)
- Step 10 commit: done | declined | failed (<reason>)
- Step 11 merge: `<branch>` | declined | failed (<reason>)
- Commit date amended: yes (`<datetime>`) | no
```

Rules:

- List every fix under **Fixes applied**.
- Do not report PASS on a file that still has unfixed syntax/semantic blockers.
- Re-run delivery diff after fixes so the commit message matches final state.
- **Never** ask Step 10 ("Should I run the git commit?") until **Commit message suggestion** is
  printed in the response above the optional-git section (or in the same message, before
  `AskQuestion`).

## Optional git steps

**Order:** validation report → **commit message shown** → Step 10 ask → (if yes) commit → Step 11 ask.

After the user has seen the **Commit message suggestion**, offer git actions via `AskQuestion`
(or equivalent explicit user approval). Do not commit or merge without approval. Do not ask to
commit in the same turn without first showing the suggested message body.

### Step 10 — Run git commit (always ask)

**Always** ask: **"Should I run the git commit?"** — but **only after** the suggested message
is visible in your prior output (title + bullet list from Step 9).

If **no** → stop. Do not ask Step 11.

If **yes** → follow the user **Git Safety Protocol** (`committing-changes-with-git` rule), except **do not run `git add`**:

1. `git status`, `git diff`, `git log -1` (parallel).
2. List delivery-scope files for the user to stage manually (warn on secrets). Wait for confirmation that they are staged, or proceed only if `git diff --cached` already contains the delivery.
3. Commit with the drafted message (HEREDOC). Never skip hooks.
4. `git status` after commit to verify success.
5. If commit **failed** (hook rejected) → fix and create a **new** commit; do not amend unless amend rules apply.

**Optional commit timestamp:** If the user supplies a datetime when approving (e.g. `2026-06-22T16:15:07-0300`), amend the **last** commit immediately after a successful commit:

```bash
GIT_COMMITTER_DATE="<datetime>" git commit --amend --no-edit --date "<datetime>"
```

Use the exact format the user gives (ISO 8601 with offset). Applies only when the user explicitly requests a backdated/amended author date.

### Step 11 — Merge into validation branch (only after Step 10 yes)

Ask **only if** Step 10 was approved **and** the commit succeeded.

Ask: **"Should I merge the current branch into the validation branch?"**

Options (via `AskQuestion`):

- `review`
- `staging`
- `qa`
- `test`
- **No / skip**

If the user picks a validation branch:

1. Record `SOURCE_BRANCH=$(git branch --show-current)` before checkout.
2. `git checkout <validation-branch>` (e.g. `review`).
3. `git merge "$SOURCE_BRANCH"` — use `-m "Merge branch '$SOURCE_BRANCH' into <validation-branch>"` for a merge commit when needed.
4. If merge fails → report conflict; do not force. Stop Step 11.
5. **Optional merge-commit timestamp:** If the user supplies a datetime for the merge commit, amend **HEAD** (the merge commit) after a successful merge:

```bash
GIT_COMMITTER_DATE="<datetime>" git commit --amend --no-edit --date "<datetime>"
```

6. Report result (`git log -1 --oneline`, current branch). Do not push unless the user asks separately.

**Notes:**

- Step 11 runs on top of the commit from Step 10 (working tree should be clean after commit).
- Never `git push --force` to validation branches unless the user explicitly requests it.
- Amending merge commit dates requires the same explicit user-provided datetime as Step 10.
