---
name: midas-validation-commit-enonic
description: Headless Enonic XP backend validation (CommonJS/ES5.1 rules) with fixes for the unstaged delivery, then write the final commit message to the COMMIT_MSG.txt path given in the prompt. Non-interactive adaptation of enonic-staged-validation-commit-message.
---

# Midas Validation + Commit Message (Enonic, headless)

Follow `../vendor/enonic-staged-validation-commit-message/SKILL.md` for the
Enonic XP backend JavaScript subset, and
`../vendor/generic-staged-validation-commit-message/SKILL.md` for every other
file in the delivery, with these **overrides for headless midas runs**:

1. **Never ask the user anything.** Skip any optional git commit / merge steps
   entirely - midas commits deterministically.
2. **Delivery scope is always the unstaged working tree**; skip the
   staged/branch-diff tiers.
3. Apply every safe fix (including Enonic CommonJS/ES5.1 rule violations);
   re-validate until clean or only unfixable blockers remain.
4. **Commit message output:** write the final commit message (subject + blank
   line + body) to the EXACT absolute `COMMIT_MSG.txt` path given in the
   prompt. The subject MUST start with the Jira issue key.
5. Git rules are absolute: never run `git add`, `git commit`, `git push`, or
   any git write command.
6. Reply with: validation verdict, fixes applied, and the commit message.
