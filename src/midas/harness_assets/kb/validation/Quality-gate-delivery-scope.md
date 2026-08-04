# Quality gate — delivery scope

**Scope:** `_shared`  
**Applies to:** `validate-qa` / aliases; `lint-and-draft-enonic-commit-message`; `lint-and-draft-generic-commit-message`; `draft-commit-message`  
**Related:** [Quality-gate-delivery-standards.md](Quality-gate-delivery-standards.md), [Quality-gate-response-template.md](Quality-gate-response-template.md)

## Target code

All validation, fixes, and commit-message drafting apply **only** to the current solution delivery. Resolve it in this order:

| Priority | Source | Git command |
|----------|--------|-------------|
| 1 | **Staged code** | `git diff --cached --name-only` and `git diff --cached` |
| 2 | **Unstaged changes** (when index is empty) | `git diff --name-only` and `git diff` |
| 3 | **Branch diff vs base** (when working tree is clean) | `git diff main...HEAD` or `git diff master...HEAD` (use whichever exists) |

Also run `git status --short` every time to confirm which case applies.

## Rules

- Prefer the **highest-priority** source that has content.
- When fixing, edit **only files in that delivery scope** unless a one-line import/caller fix is required to keep the delivery correct.
- After applying fixes, re-read / re-diff the delivery to confirm improvements and no regressions; re-validate until clean or remaining issues are reported as blockers.
- Draft commit messages from **only files in that delivery scope** (after fixes, when the skill also validates).
- If the delivery is empty, say so and skip validate/draft (tell the user which files to stage if work exists unstaged).
- Do **not** stage fixes after editing — use `git diff` (unstaged) to verify.
- **Never run `git add` or `git restore --staged`.** Leave all agent edits unstaged; the user stages manually.
