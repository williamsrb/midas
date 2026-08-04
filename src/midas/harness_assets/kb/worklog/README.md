# Worklog operations knowledge base

Current procedures for `/generate-worklogs`. This file contains the **how**:
tool discovery, evidence collection, Jira/Slack mechanics, and known limitations.
The skill contains the **what**: required behavior, attribution, output, and safety.

Last verified: 2026-08-04

## Run sequence

1. Resolve the target date and requested hours in UTC-3.
2. Run the local evidence collector.
3. Read relevant Cursor prompt results.
4. Discover and search every Slack MCP workspace.
5. Discover current Atlassian tools and retrieve existing worklogs first.
6. Collect other Jira activity for evidence candidates.
7. Match evidence, allocate remaining time, and generate the complete report.
8. If posting was requested, write and verify each worklog.
9. Apply the post-run learning protocol.

## Stable local paths

- History: `~/.cursor/history/<YYYY-MM-DD>/`
- Prompt files: `*_prompt.md`
- Outcome files: matching `*_result.md`
- Project repos: `~/Workspace/Projects/`
- Offline Jira tasks: `~/.cursor/prds/<ISSUE-KEY>.md`
- Collector:

```bash
python3 ~/.cursor/skills/generate-worklogs/scripts/collect-daily-evidence.py YYYY-MM-DD
```

The collector reports prompt paths, active repositories, commits, branch names,
remotes, and git author identity. A non-zero exit is a warning, not a reason to
skip the remaining sources.

Read prompt files in filename order. Extract intent, Jira keys, repo hints, and
outcomes from matching result files. Ignore worklog-generation prompts unless
they add evidence.

For active repositories, filter authored commits using repository git identity.
Treat other authors' commits as context only. Include uncommitted activity when
the collector reports same-day file changes.

## MCP discovery

Always call `GetDynamicTools` before `CallDynamicTool` (Cursor dynamic MCP
namespaces). Older docs named these `GetMcpTools` / `CallMcpTool` — same
sequence, updated tool surface names.

- Discover Slack servers with pattern `slack`; do not rely only on known IDs.
- Inspect the Atlassian server before choosing a worklog retrieval method.
- Prefer a dedicated current tool over a workaround when its schema and a live
  call prove it supplies the required fields.
- Authenticate a server only when it reports `needsAuth` or a call returns an
  authentication error.

Known Slack server IDs at last verification:

- `plugin-slack-slack`
- `user-slack-workspace-leanon`

Known Jira base: `https://seeds.atlassian.net`

## Slack collection

For every discovered ready Slack server, inspect the schema for:

- `slack_search_public_and_private`
- `slack_read_thread`
- `slack_read_user_profile` when identity resolution is needed

Run and paginate these searches for each workspace:

```text
from:me on:YYYY-MM-DD
to:me on:YYYY-MM-DD
from:me on:YYYY-MM-DD has:link seeds.atlassian.net
```

Use chronological sorting and concise responses when supported. Run a Jira-link
`to:me` pass when the initial evidence is sparse.

Tag every result with its MCP server ID. User IDs, channel IDs, and message
timestamps are workspace-specific. Read a thread only through the same server
that produced the search result.

Extract people, Jira keys, topics, outcomes, and relevant links. Skip greetings,
acknowledgements, scheduling chatter without substance, and unrelated bot noise.
Bot output may count when it confirms the user's CI or deployment action.

Record per-workspace message/conversation counts and success/failure state.

## Jira collection

### Identity and cloud

At last verification, use:

- `getAccessibleAtlassianResources` to resolve `cloudId`
- `atlassianUserInfo` for the current account
- `lookupJiraAccountId` only when additional identity resolution is needed
- `searchJiraIssuesUsingJql` for issue candidates
- `getJiraIssue` for issue fields and changelog
- `addWorklogToJiraIssue` for writes

Inspect live schemas because field names and available tools may change.

### Existing worklogs: current method

**Date-scoped discovery** (preferred for “what did I log on YYYY-MM-DD?”):

```jql
worklogAuthor = currentUser()
AND worklogDate >= "YYYY-MM-DD"
AND worklogDate <= "YYYY-MM-DD"
ORDER BY updated DESC
```

Request `summary`, `status`, and `worklog`. Fetch each issue explicitly when the
search response omits worklog details.

Filter embedded entries to:

- the target date interpreted in UTC-3
- the current user, using account ID when available

Retain worklog ID, `started`, duration, author, and comment. Entries returned by
the current-user JQL may display Tempo as author; do not count those twice.

Also inspect existing worklogs on issue keys discovered from other sources.

The embedded issue worklog list may be truncated (historically around 20 items).
Compare total and returned counts and warn when the target day may be absent.

**Per-issue worklog read** (verified 2026-07-31): Rovo catalog op `getIssueWorklog`
via `user-atlassian-rovo-preview` `execute`. Inputs: `issueIdOrKey` (required),
optional `startAt` / `maxResults` (default 20, max 1000). Returns `total` plus
entries with `id`, `author`, `timeSpent`, `started`, and `comment`. It does **not**
filter by date — paginate and filter locally. Use this to verify candidate issues
after JQL discovery, or when embedded `worklog` on `getJiraIssue` is truncated.
It is not a substitute for date-scoped JQL discovery.

Do not use generic Rovo search/fetch as a worklog source unless a verified schema
and live response expose the required worklog fields.

### Other Jira activity

Search same-day assigned/updated issues:

```jql
assignee = currentUser()
AND updated >= "YYYY-MM-DD 00:00"
AND updated <= "YYYY-MM-DD 23:59"
ORDER BY updated DESC
```

Search same-day transitions:

```jql
status CHANGED BY currentUser()
DURING ("YYYY-MM-DD 00:00", "YYYY-MM-DD 23:59")
ORDER BY updated DESC
```

For candidate issues, retrieve summary, status, comments, worklogs, and changelog.
Keep only the user's same-day comments/transitions. Ignore GitLab bot comments
unless they point to the user's commits.

### Posting worklogs

At last verification, create or update through `addWorklogToJiraIssue`; use a
`worklogId` when updating.

Set every target-day entry to:

```text
YYYY-MM-DDT07:00:00.000-0300
```

Never omit `started` or use an evening time. `07:00-0300` avoids calendar rollover
when Tempo/Jira stores or displays the value in a positive offset. Multiple issues
may use the same timestamp.

After each write, verify `started` resolves to the target date in UTC-3. If not,
update the same worklog ID immediately with the fixed timestamp.

## Collection status model

Track every collector as:

- `ok`: completed, including a valid empty result
- `partial`: completed with pagination, truncation, or scope uncertainty
- `failed`: call/script failed
- `skipped`: unavailable or unauthorized, with reason

An empty result is not proof of no activity when another workspace/page/source
was not queried.

## Post-run learning protocol

At the end of each run, compare observed schemas and calls to this file.

Update this KB automatically only for verified durable operational changes:

1. Edit the relevant current section so it describes one preferred method.
2. Move an obsolete method into a brief “Superseded” note only when still useful.
3. Update `Last verified`.
4. Add one changelog item containing:
   - date
   - capability or behavior observed
   - evidence: schema name plus successful/failed call result
   - procedure replaced
5. Mention the KB update in the generated report.

Do not record transient errors, unverified assumptions, secrets, tokens, user
content, issue details, or run-specific evidence. Do not automatically alter the
skill's business and output contract.

## Changelog

- **2026-08-04 — Dynamic MCP tool names:** Live session exposes
  `GetDynamicTools` / `CallDynamicTool` (not `GetMcpTools` / `CallMcpTool`).
  Evidence: successful Slack `slack_search_public_and_private` and Atlassian
  `searchJiraIssuesUsingJql` / Rovo `execute(getIssueWorklog)` via
  `CallDynamicTool`. Procedure text updated; old names marked superseded.

- **2026-07-31 — getIssueWorklog available:** Rovo `discover` returned catalog op
  `getIssueWorklog`; live `execute` on `LEARN-63` / `I99X-359` returned
  `total` + paginated worklogs (`id`, `author`, `timeSpent`, `started`,
  `comment`). No date filter — keep `worklogDate` JQL for day discovery; use
  `getIssueWorklog` for per-issue pagination after candidates are known.
  Supersedes the “no dedicated read-worklogs tool” claim from 2026-07-29.

- **2026-07-29 — What/How split:** Moved operational collection and MCP guidance
  out of the skill. Added mandatory live capability discovery and automatic,
  evidence-gated KB learning. Existing Jira worklog retrieval remains
  `worklogDate` JQL plus `getJiraIssue`; the direct-tool migration check is now
  part of every run.
