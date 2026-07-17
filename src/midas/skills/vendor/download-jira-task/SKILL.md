---
name: download-jira-task
description: >-
  Downloads Jira issue description and comments via the Atlassian MCP integration
  and saves them as a markdown file under ~/.cursor/tasks/<ISSUE-KEY>.md.
  Use when the user asks to download, fetch, export, or save Jira task details,
  ticket description, or issue comments — by issue key (e.g. AS-1171) or Jira URL
  (https://seeds.atlassian.net/browse/...).
---

# Download Jira Task

Fetch a Jira issue's **description** and **comments** from Seeds Jira and write a markdown file to the user's task cache.

**Jira base URL:** `https://seeds.atlassian.net`  
**Output directory:** `~/.cursor/tasks/` (user profile — e.g. `/home/<user>/.cursor/tasks/`)  
**Output filename:** `<ISSUE-KEY>.md` (e.g. `AS-1171.md`)

---

## Step 1 — Resolve the issue key

Accept:

- Issue key: `AS-1171`
- Browse URL: `https://seeds.atlassian.net/browse/AS-1171`

Extract with regex `[A-Z][A-Z0-9]+-\d+`. If no key is found, ask the user.

---

## Step 2 — Fetch from Jira (Atlassian MCP)

Read tool schemas under `plugin-atlassian-atlassian` before calling.

### 2a. Resolve cloudId

Try `cloudId: "seeds.atlassian.net"` first on `getJiraIssue`.

If that fails, call `getAccessibleAtlassianResources` and use the returned `id` for the Seeds site.

### 2b. Fetch issue + comments (single call)

```
CallMcpTool
  server: plugin-atlassian-atlassian
  toolName: getJiraIssue
  arguments:
    cloudId: "seeds.atlassian.net"
    issueIdOrKey: "<ISSUE-KEY>"
    responseContentFormat: "markdown"
    fields:
      - summary
      - description
      - status
      - issuetype
      - priority
      - assignee
      - reporter
      - created
      - updated
      - project
      - comment
```

Extract from the response:

| Field | Source |
|-------|--------|
| Title | `fields.summary` |
| Description | `fields.description` (markdown string) |
| Status | `fields.status.name` |
| Type | `fields.issuetype.name` |
| Priority | `fields.priority.name` |
| Project | `fields.project.name` (`fields.project.key`) |
| Reporter | `fields.reporter.displayName` |
| Assignee | `fields.assignee.displayName` (or "Unassigned") |
| Created / Updated | `fields.created`, `fields.updated` |
| Comments | `fields.comment.comments` — array sorted by `created` ascending |

Each comment object: `id`, `author.displayName`, `created`, `updated`, `body` (markdown when `responseContentFormat` is `markdown`).

If `fields.comment` is missing, make a second call with `fields: ["comment"]` only and merge.

---

## Step 3 — Write the markdown file

1. `mkdir -p ~/.cursor/tasks`
2. Write `~/.cursor/tasks/<ISSUE-KEY>.md` using the template below.
3. Tell the user the absolute path to the saved file.

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

- Preserve description and comment bodies verbatim (links, lists, blockquotes).
- Strip Jira-only blob image URLs (`blob:https://media.staging.atl-paas.net/...`) — note `(image attachment — see Jira)` when images are referenced but not downloadable.
- Convert `<custom data-type="smartlink" ...>` wrappers to plain URLs when the URL is visible in the tag.
- Do not invent acceptance criteria or implementation plans — this skill exports raw task content only.

---

## Step 4 — Confirm

Reply with:

- Issue key and Jira link
- Path to the saved file
- Brief summary: status, assignee, comment count

---

## Examples

**Input:** `https://seeds.atlassian.net/browse/AS-1171`  
**Output:** `~/.cursor/tasks/AS-1171.md`

**Input:** `download NTF-1209`  
**Output:** `~/.cursor/tasks/NTF-1209.md`

---

## Errors

| Situation | Action |
|-----------|--------|
| Issue not found | Report key tried; ask user to verify access |
| MCP auth failure | Ask user to authenticate the Atlassian plugin |
| Empty description | Write file anyway; note "No description" in that section |
| No comments | Write `## Comments (0)` with a short note |
