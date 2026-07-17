---
name: midas-jira-fallback
description: Headless fallback - download a Jira issue (description + comments) via the Atlassian MCP tools and write it as a markdown file to the exact absolute path given in the prompt. Adapted from download-jira-task for non-interactive midas runs.
---

# Midas Jira Fallback Download

You are running **headless inside midas** - never ask questions, never wait for
input. If something fails, reply `FAILED: <reason>` and stop.

## Steps

1. The prompt gives you an issue key (e.g. `RFD-123`), a Jira base URL, and an
   exact absolute destination path. Use them verbatim.
2. Fetch the issue with the Atlassian MCP Jira tools (e.g. `getJiraIssue`) with
   fields: summary, description, status, issuetype, priority, assignee,
   reporter, created, updated, project, comment, labels. If a cloudId is
   required, resolve it from the base URL host (e.g. `seeds.atlassian.net`) or
   via `getAccessibleAtlassianResources`.
3. Write the destination file (create parent dirs) using the template from
   `../vendor/download-jira-task/SKILL.md` ("Markdown template" section):
   title header, metadata block, `## Description`, `## Comments (<count>)` in
   chronological order, exported-on footer.
4. Preserve description/comment markdown verbatim; strip Jira blob image URLs,
   noting `(image attachment - see Jira)`.
5. Verify the file exists and is non-empty, then reply exactly `DONE`.

## Errors

- Issue not found / no MCP access: reply `FAILED: <short reason>`. Do NOT
  create an empty or invented file.
