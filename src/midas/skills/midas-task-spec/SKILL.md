---
name: midas-task-spec
aliases: midas-plan-implementation, midas-planner
description: Planning phase (expensive model) - turn a downloaded Jira task into a concrete implementation plan (plan.md) for the current repository. Headless adaptation of the plan-implementation skill.
---

# Midas Task Spec / Implementation Plan

You are running **headless inside midas** as the PLANNER. You are in the project
repository. Never ask questions; make the best evidence-based decision and record
assumptions explicitly.

## Context budget

The prompt already names every path you need. Reading beyond this costs the run twice,
because the implementer pays again for whatever you put in the plan.

- **Read:** the task markdown file, the environment facts JSON, and the repository files
  the task actually touches.
- **Do not read:** the whole repository, unrelated modules, prior rounds' plans (the prompt
  supplies the previous plan when it matters), or any evidence plan.
- Prefer `Grep` and targeted section reads over whole-file reads. Locate first, then read
  only what you located.
- Never search for the task file or ask for its path - the prompt is authoritative.
- Spawn no subagents unless the prompt says you may.

## What to produce

Contract conventions (user story, functional requirements, technical plan) live in
`../vendor/plan-implementation/SKILL.md` - follow its spirit, but produce a single
self-contained `plan.md` at the exact absolute path given in the prompt.

1. Read the task markdown file and the environment facts JSON (repo, stack, enonic flag,
   review URL, CI).
2. Explore the repository only as far as needed to ground the plan in real files: the
   components, controllers, content types, configs or modules the task touches. Reference
   real paths.
3. If the environment facts say the project is Enonic, read
   `../vendor/apply-react4xp-practices/SKILL.md` first and align the plan with its
   conventions.
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

5. Keep the plan minimal - the smallest diff that fully solves the requirement. No
   drive-by refactors, no "nice to have" items.
6. Reply with a one-paragraph summary of the plan.

## How-To references

Procedure lives in the knowledge base, not in this file. Consult it rather than
re-deriving it:

- `~/.cursor/kb/implementation/How-to-resolve-task-context.md` - the read-allowlist model
  this budget follows.
- `~/.cursor/kb/implementation/How-to-align-react4xp-project-to-seeds-standards.md` - when
  the plan touches project structure.
- `~/.cursor/kb/offline-reference/<catalog>/` - platform API semantics, when installed.
  Absent is fine: fall back to the repository and MCP.

## Hard rules

- Do NOT implement anything in this phase. Do NOT modify repository files.
- Do NOT run git write commands (commit/push/checkout).
- The plan must be executable by a mid-tier model without asking questions.
