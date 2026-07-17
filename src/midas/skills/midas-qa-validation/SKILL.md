---
name: midas-qa-validation
description: Headless QA validation of the current unstaged delivery - requirement fit, impact safety, code quality, less-code-is-better - with targeted fixes applied. Non-interactive adaptation of the qa-validation skill.
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
5. End with the vendor skill's QA report template. The follow-up section is
   handled by midas - do not suggest running other skills.
