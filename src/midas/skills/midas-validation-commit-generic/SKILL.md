---
name: midas-validation-commit-generic
description: Headless syntax/semantic/lint validation with fixes for the unstaged delivery (any stack), then write the final commit message to the COMMIT_MSG.txt path given in the prompt. Non-interactive adaptation of generic-staged-validation-commit-message.
---

# Midas Validation + Commit Message (generic, headless)

Follow `../vendor/generic-staged-validation-commit-message/SKILL.md` with these
**overrides for headless midas runs**:

1. **Never ask the user anything.** Skip the vendor skill's optional Steps
   10-11 (git commit / merge) entirely - midas commits deterministically.
2. **Delivery scope is always the unstaged working tree**; skip the
   staged/branch-diff tiers.
3. Apply every safe fix; re-validate until clean or only unfixable blockers
   remain (list those in your reply).
4. **Commit message output:** instead of only printing it, write the final
   commit message (subject line + blank line + body) to the EXACT absolute
   `COMMIT_MSG.txt` path given in the prompt. The subject MUST start with the
   Jira issue key (e.g. `RFD-123: short imperative summary`).
5. Git rules are absolute: never run `git add`, `git commit`, `git push`, or
   any git write command.
6. Reply with: validation verdict (PASS / PASS WITH NOTES / FAIL), the fixes
   applied, and the commit message you wrote.
