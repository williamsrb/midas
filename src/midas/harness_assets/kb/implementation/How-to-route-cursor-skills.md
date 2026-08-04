# Skill routing cheat-sheet

**Scope:** `_shared` (personal Cursor skills)  
**Applies to:** daily Enonic / mixed delivery work  
**Related:** plan `~/.cursor/plans/skill-portfolio-redesign.md`

## Which slash for which intent

| Intent | Use | Avoid confusing with |
|--------|-----|----------------------|
| Offline Jira dump | `download-jira-task` | live MCP-only fetch |
| Spec / Plan from Jira | `jira-task-spec` | download-only |
| Run an existing plan file | `run-plan` / `run-implementation-plan` / `run-test-plan` / `run-validation-plan` | inventing a plan |
| Implement from `.tasks/<KEY>.md` | `task-implementer` (+ `enonic-react4xp-best-practices`) | ad-hoc coding without spec |
| Delivery QA / “is this good enough?” / review artifact | `qa-validation` (aliases: `qa-review`, `review-task`, `task-review`) | syntax staged-validation; Bugbot built-ins |
| Syntax + commit message (Enonic backend JS) | `enonic-staged-validation-commit-message` | `qa-validation` |
| Syntax + commit message (other stacks) | `generic-staged-validation-commit-message` | enonic-staged |
| Commit message only | `staged-commit-message` | full validation skills |
| Evidence / screenshots / Jira evidence comment | `task-evidence-plan` or `run-test-plan` | unnamed browser loops |
| XP server.log / Gradle fail | `xp-app-debugger` | staged-validation |
| Sandbox / deploy CLI | `enonic-cli` | raw `enonic` from memory |
| XP7 → XP8 upgrade | `xp-app-upgrader` | minor 7.x bumps |

## Pipeline (happy path)

```text
download-jira-task → plan-implementation → run-plan (impl)
  → validate-qa → lint-and-draft-enonic|generic-commit-message
  → plan-task-evidence → run-plan (evidence)
```

User may pass **only** `<TASK-ID>` (or already be on branch/worktree `<TASK-ID>`). Skills **auto-resolve** `../../prds/<TASK-ID>.md`, `../../plans/<TASK-ID>.md`, and `../../plans/<TASK-ID>-evidence-plan.md` — do **not** solicit redundant full paths. See `How-to-resolve-task-context.md` and `How-to-optimize-agent-token-usage.md`.

## Validation vs review vs syntax

- **qa-validation** — requirements, quality, security, less-code; may fix delivery; optional `.tasks/<KEY>-review.md`. Standards: `~/.cursor/kb/validation/Quality-gate-*.md`.
- **staged-validation-*** — parse/syntax/lint + commit message draft (no commit ask). Shared How: `Quality-gate-delivery-scope.md`.
- **staged-commit-message** — message draft only (no commit ask).
- **Bugbot / security review** — Cursor built-ins; escalate from QA when needed.

## Other shared How pointers

- Jira offline fetch: `How-to-fetch-jira-issue-via-atlassian-mcp.md` (`download-jira-task`)
- Enonic CLI catalogs: `implementation/enonic-cli/`
- XP debug logs: `How-to-debug-xp-server-logs.md`
- XP8 upgrade catalogs: `How-to-run-xp8migrator.md` + `xp7-to-xp8-upgrade/`
- React4XP Seeds alignment: `How-to-align-react4xp-project-to-seeds-standards.md`
- XP testing recipes: `testing/_shared/How-to-test-enonic-xp-apps.md`

## Pitfalls

- Saying “validate” without context can hit QA or staged-validation — pick from the table.
- `review-task` / review mode is the same `validate-qa` skill (chat report vs optional `.tasks/<KEY>-review.md` artifact). No separate Codex reviewer path.
- Re-attaching full PRD + impl plan + evidence plan on every step wastes tokens — follow per-skill allowlists in `How-to-resolve-task-context.md`.
