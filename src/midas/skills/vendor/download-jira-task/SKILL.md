---
name: download-jira-task
aliases: fetch-jira-task, export-jira-task, save-jira-task, jira-task-offline
description: >-
  Downloads Jira issue description and comments via the Atlassian MCP integration
  and saves them as a markdown file under ../../prds/<ISSUE-KEY>.md.
  Use when the user asks to download, fetch, export, or save Jira task details,
  ticket description, or issue comments — by issue key (e.g. AS-1171) or Jira URL
  (https://seeds.atlassian.net/browse/...). After a standalone download, may offer
  to continue into plan-implementation (skipped when nested from that skill).
---

# Download Jira Task

Fetch a Jira issue's **description** and **comments** from Seeds Jira and write a markdown file to the user's task cache.

**Jira base URL:** `https://seeds.atlassian.net`  
**Output directory:** `../../prds/` (relative to this skill)  
**Output filename:** `<ISSUE-KEY>.md` (e.g. `AS-1171.md`)

## Context budget (token)

1. Resolve `<TASK-ID>` via `../../kb/implementation/How-to-resolve-task-context.md`
2. Open **only** allowlisted paths for this skill (write/read this task's PRD only)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. Do **not** read other tasks' PRDs, impl plans, or evidence plans

## Knowledge base (mandatory How)

MCP fetch mechanics (cloudId, `getJiraIssue` fields, extraction, auth errors):

`../../kb/implementation/How-to-fetch-jira-issue-via-atlassian-mcp.md`

This skill owns the offline file contract, template, and cascade rules below. The KB owns live tool usage.

### Nested vs standalone

| Mode | How to detect | After save |
|------|---------------|------------|
| **Nested** (prerequisite) | Caller stated `called_from: plan-implementation`, or the active skill flow is clearly `plan-implementation` ensuring an offline copy exists | Confirm path only — **do not** prompt to cascade into `plan-implementation` |
| **Standalone** | User invoked this skill directly | After confirm, **ask** whether to continue into `plan-implementation` (Step 5) |

If an offline file already exists and the user did **not** ask for a newer version, prefer using it (or skip re-download) — still apply Step 5 cascade rules for standalone runs when the file is ready.

## Step 1 — Resolve the issue key

Resolve `<TASK-ID>` per `How-to-resolve-task-context.md` (message key/URL → branch → worktree folder → ask once). Do not ask for full PRD/plan paths.

## Step 2 — Fetch from Jira

Follow the KB How-to. Do not invent fields or skip comment `id`s.

## Step 3 — Write the markdown file

1. Ensure `../../prds/` exists; write `../../prds/<ISSUE-KEY>.md`.
2. Tell the user the absolute path.

### Markdown template

```markdown
# <ISSUE-KEY> — <summary>

**Jira:** https://seeds.atlassian.net/browse/<ISSUE-KEY>
**Project:** <project name> (<project key>)
**Type:** <issuetype>
**Status:** <status>
**Priority:** <priority>
**Reporter:** <reporter>
**Assignee:** <assignee>
**Created:** <created>
**Updated:** <updated>

---

## Description

<fields.description — preserve markdown as-is>

---

## Comments (<count>)

<For each comment, in chronological order:>

### Comment <id> — <author.displayName> — <created ISO date>

<body — preserve markdown as-is>

---

*Exported from Jira on <today's date>*
```

**Formatting rules:**

- Preserve description and comment bodies verbatim.
- Strip Jira-only blob image URLs (`blob:https://media.staging.atl-paas.net/...`) — note `(image attachment — see Jira)` when needed.
- Convert `<custom data-type="smartlink" ...>` wrappers to plain URLs when visible.
- Do not invent acceptance criteria or implementation plans.

## Step 4 — Confirm

Reply with issue key + Jira link, saved path, and brief summary (status, assignee, comment count).

## Step 5 — Cascade into `plan-implementation` (standalone only)

**Skip** when nested (`called_from: plan-implementation`).

When standalone and the file is ready, ask (prefer `AskQuestion`):

> Offline copy saved. Continue into **plan-implementation** to draft the implementation spec under the agent plans dir (`../../plans/<ISSUE-KEY>.md`)?

- **Yes** — follow `plan-implementation` next (must **not** re-download).
- **No** — stop.

Do **not** auto-start `plan-implementation` without approval.

## Examples

**Input:** `https://seeds.atlassian.net/browse/AS-1171` → `../../prds/AS-1171.md`  
**Input:** `download NTF-1209` → `../../prds/NTF-1209.md`

## Errors

| Situation | Action |
|-----------|--------|
| Issue not found / MCP auth | Per KB How-to |
| Empty description | Write file; note "No description" |
| No comments | Write `## Comments (0)` with a short note |
