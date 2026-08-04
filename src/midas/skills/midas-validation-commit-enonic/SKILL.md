---
name: midas-validation-commit-enonic
aliases: midas-lint-and-draft-enonic-commit-message
description: Headless Enonic XP backend validation (CommonJS/ES5.1 rules) with fixes for the unstaged delivery, then write the final commit message to the COMMIT_MSG.txt path given in the prompt. Non-interactive adaptation of lint-and-draft-enonic-commit-message.
---

# Midas Validation + Commit Message (Enonic, headless)

Follow `../vendor/lint-and-draft-enonic-commit-message/SKILL.md` for the
Enonic XP backend JavaScript subset, and
`../vendor/lint-and-draft-generic-commit-message/SKILL.md` for every other
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

## Context budget

- **Read:** the unstaged diff, and the Enonic-subset files it touches.
- **Do not read:** the PRD, the plan, or files outside the delivery.
- The delivery-scope definition is a versioned quality gate, not a judgement call:
  `~/.cursor/kb/validation/Quality-gate-delivery-scope.md`.
- Enonic rule specifics (Nashorn template strings, Thymeleaf negation) have KB entries -
  `~/.cursor/kb/implementation/How-to-negate-booleans-in-thymeleaf-th-if.md` and the
  matching rules under `~/.cursor/rules/enonic-*.mdc`. Consult, do not re-derive.
