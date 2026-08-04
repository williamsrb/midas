# Quality gate — response template

**Scope:** `_shared`  
**Applies to:** delivery QA / review skills (`qa-validation` and aliases)  
**Related:** [Quality-gate-delivery-standards.md](Quality-gate-delivery-standards.md)

Use this structure for chat QA reports:

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

### Performance
- <finding> — or "None"

### Security
- <finding> — or "None"

### Follow-up
- Run `enonic-staged-validation-commit-message` (Enonic backend JS) or `generic-staged-validation-commit-message` (other stacks) next — both validate **and fix** syntax/semantics/lint, then draft the commit message. For message-only, use `staged-commit-message`.
- Review artifact path (review mode): `.tasks/<KEY>-review.md` or `tasks/<KEY>-review.md` — or "n/a"
- Escalate to Bugbot / Security Review built-ins only if requested or clearly needed
- <optional action items if FAIL or PASS WITH NOTES>
```

## Reporting rules

- Be concise; bullets over long prose.
- Separate confirmed facts from assumptions.
- List every source edit under **Fixes applied** (file + brief reason).
- If validation is incomplete (e.g. missing runtime test), say so explicitly.
- If no fixes were needed, say `None` under **Fixes applied**.
- Re-run delivery diff commands after fixes so the report reflects final state.
