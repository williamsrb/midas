---
name: midas-qa-validation
description: Headless QA validation of the current unstaged delivery - requirement fit, impact safety, code quality, less-code-is-better, plus performance and security review - with targeted fixes applied. Non-interactive adaptation of the qa-validation skill.
---

# Midas QA Validation (headless)

Follow `../vendor/qa-validation/SKILL.md` in full, with these **overrides for
headless midas runs**:

1. **Never ask the user anything.** Apply every fix that the vendor skill's
   Fix policy allows; report (don't apply) anything riskier.
2. **Delivery scope is always the unstaged working tree** (`git status --short`
   + `git diff`) - midas guarantees the index is empty at this point. Skip the
   staged/branch-diff tiers.
3. The **requirement** is the Jira task file whose path is given in the prompt
   (plus the plan.md if referenced). Restate it yourself; no user to confirm.
4. Git rules are absolute: never run `git add`, `git commit`, `git push`,
   `git restore`, or any git write command. Leave everything unstaged.
5. End with the vendor skill's QA report template, adding the two extra
   sections below. The follow-up section is handled by midas - do not suggest
   running other skills.

## Additional review pass: performance

Within the delivery scope only, check and fix when safe:

- Queries/IO inside loops (N+1 patterns, repeated fetches of the same data) -
  hoist or batch when the fix stays local to the delivery.
- Unbounded result sets where the surrounding code paginates or limits.
- Repeated expensive computation of the same value - reuse the first result.
- Accidentally quadratic constructs introduced by the delivery (nested scans
  over the same collection) when a map/set lookup is the obvious local fix.
- Blocking work added to hot paths the diff touches (sync IO in request
  handlers) - flag it; only fix when the codebase already has the async/cached
  counterpart in use elsewhere.

## Additional review pass: security

Within the delivery scope only, check and fix when safe:

- Injection: user input concatenated into SQL/NoQL/DSL queries, shell
  commands, file paths (traversal), or HTML (XSS - escape or use the
  project's sanitizer; for Enonic, no unescaped request params into portal
  responses).
- Secrets: any credential, token, or API key hard-coded in the delivery -
  replace with the project's config mechanism and flag as Blocker.
- AuthZ: new endpoints/services/handlers exposed without the permission
  checks equivalent code in this project applies.
- Unsafe deserialization or `eval`-like constructs on external input.
- Sensitive data (passwords, tokens, personal data) written to logs.

## Hard constraint for both passes

**Never break existing contracts or the Jira task requirements**: no changes
to public function signatures, exported module APIs, HTTP routes/status
codes, schemas, content types, or persisted data formats. Performance and
security fixes must be behavior-preserving for every existing caller; when a
real fix would require a contract change, report it as a Concern with a
suggested follow-up task instead of applying it.
