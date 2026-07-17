---
name: midas-env-detect
description: LLM fallback for environment detection - read a Jira task markdown file and extract the git repository and review environment URL as strict JSON. Used only when midas' deterministic detectors find nothing.
---

# Midas Environment Detection (LLM fallback)

You are running **headless inside midas**. Deterministic regex detection
already failed, so read the task file carefully - the repo may be referenced
indirectly ("the booking site", a GitLab MR link, a project name in a comment).

## Inputs (from the prompt)

- Path to the task markdown file (description + comments)
- Git host (e.g. `git.seeds.no`) and clone template (e.g. `git@git.seeds.no:seeds/{project}.git`)

## What to find

1. **repo_url** - the ssh clone URL of the project's git repository.
   - Direct mentions: any `https://git.seeds.no/seeds/xyz...` link (also inside
     MR/pipeline URLs) -> normalize to `git@git.seeds.no:seeds/xyz.git`.
   - Indirect mentions: project names, related issue keys, deployment names.
     Map them onto the clone template. Prefer evidence from the newest comments.
   - You may verify a candidate with `git ls-remote <url>` (read-only).
2. **review_url** - the base URL of the review/staging environment if
   mentioned (e.g. `https://review.as.k8s.seeds.no/`).

## Output contract (strict)

Reply with ONLY this JSON object - no prose, no code fences:

```
{"repo_url": "git@git.seeds.no:seeds/<project>.git", "review_url": "https://...", "notes": "<one line of evidence>"}
```

- Omit nothing; use `""` for values you could not determine.
- Never invent a repo that you have no evidence for - `""` is the correct
  answer when unsure (midas will block the task for a human to resolve).
