---
name: 99x-jira-task-spec
description: "Use this skill whenever the user mentions a Jira task, ticket, or issue — whether by ID (e.g., PROJ-123) or by URL. This skill fetches the task title, description, acceptance criteria, and comments from Jira via the Atlassian MCP, then generates or updates a structured Markdown spec file at .tasks/ISSUE-KEY.md. The spec includes user stories, functional requirements, and a technical implementation plan designed to guide a subsequent AI coding session. Trigger this skill whenever the user says things like: read the Jira task, prepare the spec for PROJ-123, fetch the ticket, generate the task doc, pull the issue from Jira, or any similar phrasing referencing a Jira issue. Installed for Cursor IDE from git.seeds.no/seeds/enonic-skills."
compatibility: Claude Code, Cursor
---

## Cursor IDE

Adapted from [git.seeds.no/seeds/enonic-skills](https://git.seeds.no/seeds/enonic-skills).

**Atlassian MCP (Cursor):** Read tool schemas under the Atlassian MCP server before calling.

1. Resolve `cloudId` — `CallMcpTool` → server `plugin-atlassian-atlassian`, tool `getAccessibleAtlassianResources` (or use a known cloud ID from prior sessions).
2. Fetch issue — `CallMcpTool` → tool `getJiraIssue` with `cloudId`, `issueIdOrKey`, and optionally `responseContentFormat: "markdown"`.
3. Fetch comments — same tool with `fields: ["comment"]`.

Write the spec with **Write** / **StrReplace**. Use **Shell** for `mkdir -p .tasks` and file checks.

# Jira Task Spec Generator

Generates (or updates) a structured Markdown file at `.tasks/<ISSUE-KEY>.md` from a Jira issue.
This file serves as the **canonical input** for a subsequent implementation skill.

---

## Step 1 — Extract the Issue Key

The user may provide:
- A direct ID: `NLA-123`
- A URL: `https://company.atlassian.net/browse/NLA-123`

Extract the issue key using the regex: `[A-Z]+-\d+`. If it cannot be determined, ask the user.

---

## Step 2 — Fetch data from Jira via MCP

Use the Atlassian MCP in Cursor (`CallMcpTool`, server `plugin-atlassian-atlassian`).

### 2a. Fetch issue details

```
getJiraIssue
  cloudId: "<cloud-id>"
  issueIdOrKey: "<ISSUE-KEY>"
  responseContentFormat: "markdown"
```

Fields to extract from the response:
- `fields.summary` → task title
- `fields.description` → full description (convert ADF to clean text if needed)
- `fields.assignee.displayName` → assignee
- `fields.labels` → list of labels
- `fields.issuetype.name` → Jira issue type (used to help classify the task category below)
- **Acceptance criteria**: look in common custom fields:
  - `fields.customfield_10016` (Acceptance Criteria)
  - `fields.customfield_10014`
  - Or inside `fields.description` itself if it contains an "Acceptance Criteria" section

### 2b. Fetch comments (separate call required)

Comments are **not** included in the default issue response. Make a second call explicitly requesting the `comment` field:

```
getJiraIssue
  cloudId: "<cloud-id>"
  issueIdOrKey: "<ISSUE-KEY>"
  fields: ["comment"]
```

The response will contain `fields.comment.comments` — an array of comment objects. Each comment has:
- `author.displayName` — who wrote it
- `created` — ISO 8601 timestamp
- `body` — **always returned as an ADF JSON object** (even with `responseContentFormat: "markdown"`), with shape `{ type, version, content: [...] }`

**Extracting text from ADF body:** Walk the `content` array recursively. Collect the `text` value from every node where `type === "text"`. Concatenate them preserving paragraph breaks. Ignore nodes of type `inlineCard`, `mention`, `emoji`, `media`, and `mediaSingle`.

### 2c. Process comments

**Important:** Comments are used **only internally** to refine and supplement the acceptance criteria — they are NOT displayed in the output document (except in the temporary Raw Comments debug section). Process them as follows:

- Ignore automated CI/CD, deploy bot, and status-change comments (author name contains "Bot", "GitLab", "GitHub", "Jenkins", "Bamboo", or similar)
- Look for any requirement changes, clarifications, or new conditions added by stakeholders or the team
- If a comment contradicts or extends the original description, **treat the comment as the authoritative version** and update the acceptance criteria accordingly
- Mark criteria inferred or updated from comments with `_(from comments)_`

### 2d. Classify the task type

Analyze the issue title, description, and labels and pick **exactly one** category. This value goes in the `Type` field of the generated document and determines which reference file to load in Step 4.

| Category | When to use | Reference file |
|---|---|---|
| **New Component** | Task creates a brand-new component, part, layout, macro, or page template | `references/new-component.md` |
| **Existing Component Change** | Task modifies, fixes, or extends a component that already exists in the project | `references/change-existing.md` |
| **API Integration** | Task involves connecting to or consuming an external/internal API, webhooks, data fetching, or service integration | `references/api-integration.md` |
| **Performance / Security** | Task focuses on optimizing performance or hardening security | `references/performance-security.md` |

If the task fits more than one category, pick the **primary** intent. If truly ambiguous, default to **Existing Component Change**.

**Load the matching reference file now** — you will need its guidance to fill the `Suggested Technical Approach` and `Implementation Steps` sections in Step 5.

### 2e. Check for a prototype component (New Component and Existing Component Change only)

Skip this step if the task type is **API Integration** or **Performance / Security**.

1. Run the following command from the project root to sync prototype assets:
   ```bash
   make copyComponents
   ```
2. Determine the component's kebab-case name from the issue title (same parsing as the reference files), then convert it to **PascalCase** for the prototype path. Examples: `hero` → `Hero`, `info-card` → `InfoCard`.
3. Check whether a frontend component file exists at:
   ```
   xp/src/main/resources/react4xp/components/prototype/<PascalName>/index.tsx
   ```
   Also check `index.jsx` and `index.js` if `index.tsx` is not found.
4. If a prototype file is found:
   - Record its path as `<prototype-component-path>`.
   - Read the file and check if it exports a TypeScript interface (e.g., `export interface <Name>Props { ... }`). If one is found, record it as `<prototype-props-interface>`.
5. This information is used in the Implementation Plan (see Step 4).

---

## Step 3 — Check if the file already exists

Check whether `.tasks/<ISSUE-KEY>.md` already exists:

```bash
ls .tasks/<ISSUE-KEY>.md 2>/dev/null
```

- **If it does not exist**: create the file from scratch using the template below
- **If it already exists**: read the current file, preserve the `## Implementation Plan` section if it has been manually edited by the user (check for content beyond the default template), and update the Jira data with the latest information

Create the folder if needed:
```bash
mkdir -p .tasks
```

---

## Step 4 — Generate the Markdown

Use the template below. Fill in all fields with the collected data.
The output file must always be written in English, regardless of the language used in the Jira issue or by the user.

```markdown
# <ISSUE-KEY>: <Task Title>

| Field    | Value              |
|----------|--------------------|
| Type     | <task category — see classification rules below>   |
| Assignee | <assignee>         |

---

## Overview

<2-3 sentences summarizing what this task is about, the problem it solves, and who it affects.>

---

## User Stories

### US-001: <Short title>
**Description:** As a <user type>, I want <action> so that <benefit>.

**Acceptance Criteria:**
- [ ] <Specific, verifiable criterion — mark with `_(inferred)_` if not explicit, or `_(from comments)_` if sourced from comments>
- [ ] ...

<Repeat US-00N blocks as needed. Each meaningful user-facing behavior should have its own story.>

---

## Functional Requirements

- **FR-1:** <Explicit system behavior or constraint>
- **FR-2:** <...>

> Derived from the description, acceptance criteria, and comments. Number them for easy reference in the implementation plan.

---

## Non-Goals

> What this task explicitly does NOT include. Helps prevent scope creep.

- <Out-of-scope item>
- <...>

---

## Implementation Plan

> This section is auto-generated. Review and adjust before using it as an implementation guide.

### Problem Understanding

<2-3 paragraphs analyzing what needs to be done, the problem context, and the expected impact.>

### Suggested Technical Approach

<Fill using the reference file loaded in Step 2d. Follow its "Suggested Technical Approach — content to generate" section exactly.>

<If a prototype component was found in Step 2e, add a "Prototype Component" sub-section:>

**Prototype Component**: `<prototype-component-path>`

The frontend component already exists as a prototype. The Enonic view must render this component — do not create a duplicate React component.

<If <prototype-props-interface> was found:>

**Props contract**: The prototype file exports `<prototype-props-interface>`. This interface is the authoritative source for the props the processor must return. Do NOT generate a separate `*Props` interface in the Enonic `.d.ts` file — use or re-export the prototype interface instead, and remove any auto-generated `*Props` interface if it already exists.

<End prototype section>

### Implementation Steps

<Fill using the reference file loaded in Step 2c. Follow its "Implementation Steps — content to generate" section. Reference FR numbers where applicable.>

### Definition of Done

<Fill using the reference file loaded in Step 2c. Use its "Definition of Done checklist to include" section as the base, then add any criteria specific to this task's acceptance criteria.>

---

_Generated at: <current date and time in YYYY-MM-DD HH:MM format>_
_Source: [<ISSUE-KEY>](<full Jira issue URL>)_


```

---

## Step 5 — Save and confirm

1. Write the final content to `.tasks/<ISSUE-KEY>.md`
2. Report to the user:
   - The path of the generated file
   - A 1-2 line summary of what was found in the task
   - Whether the file was **created** or **updated**
   - Any data that was not found (e.g., no explicit acceptance criteria)
   - Whether any comments influenced the acceptance criteria

---

## Quality Notes

- **Language**: The generated Markdown file must always be in English, even if the Jira issue content or user messages are in another language. Translate descriptions, comments, and criteria as needed.
- **Atlassian Document Format (ADF)**: The Jira API returns descriptions in ADF (JSON). Convert to readable Markdown — do not dump raw JSON into the file.
- **Comments drive criteria**: Comments are the most recent source of truth for requirements. Always process them before finalizing acceptance criteria. Do not surface raw comments in the output — absorb their intent into the criteria.
- **Inferred criteria**: When no explicit criteria exist, generate them from the description and clearly mark them with `_(inferred)_`.
- **User stories**: Break the task into small, specific stories. Each should represent one user-facing behavior. Avoid mega-stories that bundle multiple unrelated behaviors.
- **Functional requirements**: Extract explicit system behaviors from the description and criteria. Number them (FR-1, FR-2, ...) so implementation steps can reference them precisely.
- **Non-goals**: Always include at least one non-goal to clarify scope boundaries. Infer from context if not stated.
- **Implementation plan**: Be concrete and technical. Avoid vague statements like "implement the feature". Analyze the task context to suggest specific files, functions, or application layers likely to be affected.
- **Idempotency**: Running the skill twice on the same task should produce an equivalent file — do not duplicate sections or erase manual edits the user has made to the Implementation Plan.
- **Prototype component**: If a prototype file was found in Step 2e, the spec must instruct the implementer to use that file as the rendered component, not create a new one. The prototype file is the source of truth for the frontend implementation.
- **Prototype props interface**: If the prototype file exports a props interface, that interface is authoritative. The spec must explicitly state that any auto-generated `*Props` interface in the Enonic `.d.ts` should be removed or not created, and the prototype interface should be used (or re-exported) instead.
