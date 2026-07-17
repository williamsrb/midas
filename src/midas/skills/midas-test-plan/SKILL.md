---
name: midas-test-plan
description: Generate a human-readable test plan plus runnable Playwright specs for a task's review environment, written into the task's test-plan directory. The developer runs them later with `midas test <KEY>` once the gitlab-ci pipeline has deployed the review branch.
---

# Midas Test Plan (Playwright)

You are running **headless inside midas**. The implementation is done and
committed locally; the review environment will only have it AFTER a human
merges the branch and the pipeline deploys. So: **generate** tests now, do not
run them against the review URL.

## Inputs (from the prompt)

- Task markdown file and environment facts JSON (contains `review_url`)
- Destination directory for all output

## Output files (write into the destination directory)

1. `TEST_PLAN.md` - human-readable plan:
   - What to verify, derived from the task's acceptance criteria/description
   - Preconditions (auth, test data) and the review base URL
   - One section per scenario: steps + expected result
2. `playwright.config.ts` - minimal config; `use.baseURL` set to the review
   URL; single chromium project; `testDir: '.'`.
3. `<issue-key-lowercase>.spec.ts` - one `test()` per scenario from the plan.
   - Selector strategy: prefer role/text selectors; keep selectors resilient.
   - Scenarios that need authentication or manual data you cannot know:
     generate the test with `test.fixme()` and a comment explaining what a
     human must fill in - never invent credentials.
4. If the knowledge base at `~/.cursor/kb/` has How-To guides for this project
   (URL patterns, auth realms, selectors), read and reuse them for realistic
   flows and selectors.

## Hard rules

- Never ask questions; never run the tests; never modify repository files.
- Tests must be runnable offline-from-repo: only `@playwright/test` imports.
- Reply with a summary: scenarios generated, which are `fixme` and why.
