# How to fetch a Jira issue via Atlassian MCP

**Scope:** `_shared` (Seeds Jira)  
**Applies to:** `download-jira-task`, any skill that needs live issue + comments before writing an offline PRD  
**Related:** offline cache `~/.cursor/prds/<ISSUE-KEY>.md`; skill `download-jira-task` owns the file template and cascade rules

## Prerequisites

- Atlassian MCP available (`plugin-atlassian-atlassian` or current Atlassian namespace).
- Always discover tool schemas (`GetDynamicTools`) before `CallDynamicTool`.
- Jira base: `https://seeds.atlassian.net`

## Resolve cloudId

1. Try `cloudId: "seeds.atlassian.net"` first on `getJiraIssue`.
2. If that fails, call `getAccessibleAtlassianResources` and use the returned `id` for the Seeds site.
3. Authenticate only when the namespace reports `needsAuth` or a call returns an auth error (`mcp_auth`).

## Fetch issue + comments

Prefer a single `getJiraIssue` call with markdown bodies:

```text
CallDynamicTool
  namespace: plugin-atlassian-atlassian
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

Older docs may show `CallMcpTool` / `server:` — same call via the current dynamic MCP surface.

## Field extraction

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

## Errors

| Situation | Action |
|-----------|--------|
| Issue not found | Report key tried; ask user to verify access |
| MCP auth failure | Ask user to authenticate the Atlassian plugin |
| Empty description / no comments | Still usable; callers write empty sections explicitly |
