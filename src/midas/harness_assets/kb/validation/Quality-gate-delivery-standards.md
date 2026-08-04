# Quality gate — delivery standards

**Scope:** `_shared`  
**Applies to:** delivery QA / review skills (`qa-validation` and aliases); other skills may reuse these standards when validating a delivery  
**Related:** [Quality-gate-delivery-scope.md](Quality-gate-delivery-scope.md), [Quality-gate-response-template.md](Quality-gate-response-template.md)

## Hard constraint on every fix

Never break existing contracts or the stated task requirements — no changes to public function signatures, exported module APIs, HTTP routes/status codes, schemas, content types, or persisted data formats. Fixes must be behavior-preserving for every existing caller. When a real fix would require a contract change, report it as a Concern with a suggested follow-up instead of applying it.

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

## Performance

Within the delivery scope only, check and fix when safe:

- Queries/IO inside loops (N+1 patterns, repeated fetches of the same data) — hoist or batch when the fix stays local to the delivery.
- Unbounded result sets where the surrounding code paginates or limits elsewhere.
- Repeated expensive computation of the same value — reuse the first result.
- Accidentally quadratic constructs introduced by the delivery (nested scans over the same collection) when a map/set lookup is the obvious local fix.
- Blocking work added to hot paths the diff touches (sync IO in request handlers) — flag it; only fix when the codebase already has the async/cached counterpart in use elsewhere.

Flag as Blocker/Concern/Note like any other finding; fix only when the change stays local and behavior-preserving (see hard constraint above).

## Security

Within the delivery scope only, check and fix when safe:

- Injection: user input concatenated into SQL/NoQL/DSL queries, shell commands, file paths (traversal), or HTML (XSS — escape or use the project's sanitizer).
- Secrets: any credential, token, or API key hard-coded in the delivery — replace with the project's config mechanism and flag as **Blocker**.
- AuthZ: new endpoints/services/handlers exposed without the permission checks equivalent code in this project applies.
- Unsafe deserialization or `eval`-like constructs on external input.
- Sensitive data (passwords, tokens, personal data) written to logs.

Flag as Blocker/Concern/Note like any other finding; fix only when the change stays local and behavior-preserving (see hard constraint above). Hard-coded secrets are always a Blocker regardless of fix feasibility.
