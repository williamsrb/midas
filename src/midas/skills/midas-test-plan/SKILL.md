---
name: midas-test-plan
aliases: midas-plan-task-evidence, midas-evidence-plan
description: Generate a human-readable test plan plus runnable Playwright specs for a task's review environment, written into the task's test-plan directory. The developer runs them later with `midas test <KEY>` once the gitlab-ci pipeline has deployed the review branch.
---

# Midas Test Plan (Playwright)

You are running **headless inside midas**. The implementation is done and committed
locally; the review environment will only have it AFTER a human merges the branch and the
pipeline deploys. So: **generate** tests now, do not run them against the review URL.

The planning conventions live in `../vendor/plan-task-evidence/SKILL.md` - follow its
scenario derivation and evidence discipline, but produce the runnable artefacts below
instead of a Jira-facing evidence plan.

## Context budget

- **Read:** the task markdown file, the environment facts JSON, and any KB testing guide
  for this project.
- **Do not read:** the implementation diff, the plan, or the repository - scenarios come
  from acceptance criteria, not from the code you are about to verify.
- Consult the KB before inventing selectors or URL shapes.

## Inputs (from the prompt)

- Task markdown file and environment facts JSON (contains `review_url`)
- Destination directory for all output

## Output files (write into the destination directory)

1. `TEST_PLAN.md` - human-readable plan:
   - What to verify, derived from the task's acceptance criteria/description
   - Preconditions (auth, test data) and the review base URL
   - One section per scenario: steps + expected result
2. `playwright.config.ts` - minimal config; `use.baseURL` set to the review URL; single
   chromium project; `testDir: '.'`.
3. `<issue-key-lowercase>.spec.ts` - one `test()` per scenario from the plan.
   - Selector strategy: prefer role/text selectors; keep selectors resilient.
   - Scenarios needing authentication or manual data you cannot know: generate the test
     with `test.fixme()` and a comment explaining what a human must fill in - never invent
     credentials.

## How-To references

The knowledge base holds the per-project instrumentation knowledge that makes these tests
realistic instead of generic:

- `~/.cursor/kb/testing/<project>/How-to-*.md` - real URL patterns, auth realms, selectors
  and test data for that client's environments. Read the one matching this project before
  writing selectors.
- `~/.cursor/kb/testing/_shared/` - conventions shared across projects.
- `~/.cursor/kb/offline-reference/content-studio-*/` - when a scenario drives Content
  Studio create/edit/publish.

Absent guides are not an error; generic-but-resilient selectors plus `test.fixme()` for
what you cannot know is the correct fallback.

## Hard rules

- Never ask questions; never run the tests; never modify repository files.
- Tests must be runnable offline-from-repo: only `@playwright/test` imports.
- Reply with a summary: scenarios generated, which are `fixme` and why.
