---
name: midas-task-spec
description: Planning phase (expensive model) - turn a downloaded Jira task into a concrete implementation plan (plan.md) for the current repository. Adapted from 99x-jira-task-spec for non-interactive midas runs.
---

# Midas Task Spec / Implementation Plan

You are running **headless inside midas** as the PLANNER. You are in the
project repository. Never ask questions; make the best evidence-based decision
and record assumptions explicitly.

The richer spec conventions live in `../vendor/99x-jira-task-spec/SKILL.md` -
follow its spirit (user story, functional requirements, technical plan) but
produce a single self-contained `plan.md` at the exact absolute path given in
the prompt.

## Steps

1. Read the task markdown file and the environment facts JSON given in the
   prompt (repo, stack, enonic flag, review URL, CI).
2. Explore the repository enough to ground the plan in real files: locate the
   components, controllers, content types, configs, or modules the task
   touches. Reference real paths.
3. If the project is Enonic (env facts say so), read
   `../vendor/99x-enonic-react4xp-best-practices/SKILL.md` first and align the
   plan with its conventions.
4. Write the plan file with EXACTLY these sections:

```markdown
# <ISSUE-KEY> - Implementation Plan

## Requirement
<2-5 sentences restating what must be delivered, from the task + comments>

## Assumptions
<bullet list; every gap in the spec becomes an explicit assumption>

## Changes
<ordered list; each item: file path (existing or new) + what changes and why>

## Out of scope
<what this plan deliberately does not touch>

## Validation
<how the implementer verifies the result: build command, tests to run/add,
 manual checks against the review environment>
```

5. Keep the plan minimal - smallest diff that fully solves the requirement.
   No drive-by refactors, no "nice to have" items.
6. Reply with a one-paragraph summary of the plan.

## Hard rules

- Do NOT implement anything in this phase. Do NOT modify repository files.
- Do NOT run git write commands (commit/push/checkout).
- The plan must be executable by a mid-tier model without asking questions.
