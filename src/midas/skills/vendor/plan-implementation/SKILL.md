---
name: plan-implementation
aliases: plan-task-spec, plan-spec, task-spec-plan, jira-task-spec
description: "Use this skill whenever the user mentions a Jira task, ticket, or issue — whether by ID (e.g., PROJ-123) or by URL. Ensures an offline copy exists via download-jira-task (../../prds/<KEY>.md), then generates or updates a structured Markdown spec under the agent plans dir (../../plans) as ISSUE-KEY.md (user stories, functional requirements, technical implementation plan). Trigger when the user says: read the Jira task, prepare the spec for PROJ-123, fetch the ticket, generate the task doc, pull the issue from Jira, or similar. Installed for Cursor IDE from git.seeds.no/seeds/enonic-skills."
compatibility: Claude Code, Cursor
---

## Cursor IDE

Adapted from [git.seeds.no/seeds/enonic-skills](https://git.seeds.no/seeds/enonic-skills).

**Offline task cache:** `../../prds/<ISSUE-KEY>.md` (produced by `download-jira-task`).  
**Plan / spec output:** `<plans-dir>/<ISSUE-KEY>.md` (see Plans directory below)  
**Enonic offline docs (XP7 / XP8 / React4XP v5 / v6 / v7):** see Step 3c — route via `../../kb/offline-reference/{xp7,xp8,react4xp-5.x,react4xp-6.x,react4xp-stable}/llm-index.md`.

Write the spec with **Write** / **StrReplace**. Use **Shell** for `mkdir -p <plans-dir>` and file checks. Do **not** call SwitchMode / ask to switch to Plan mode.

## Context budget (token)

1. Resolve `<TASK-ID>` via `../../kb/implementation/How-to-resolve-task-context.md`
2. Open **only** the allowlisted paths for this skill (see that How-to)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. Default allowlist: sectioned `../../prds/<TASK-ID>.md` → write `../../plans/<TASK-ID>.md`. Do not read evidence plans or sibling PRDs

## Auxiliary skills (optional, on demand)

Not required for every run. When a planning step needs a specialized capability you cannot perform with already-installed skills / MCP / normal tools, and a session-only script is not worth it:

1. Prefer an already-installed skill if one covers the need.
2. Otherwise follow the `find-skills` skill as a nested prerequisite (`called_from: plan-implementation`): search, verify quality, install if appropriate, then **read and follow** the new skill for the blocked action.
3. Resume this skill’s workflow after the gap is closed.

Example: the issue references a `.fig` / Figma file and no Figma reader is installed → `find-skills` → install/use a reader → continue the spec.

# Jira Task Spec Generator

Generates (or updates) a structured Markdown file at `<plans-dir>/<ISSUE-KEY>.md` from the offline Jira task copy.
This file serves as the **canonical input** for `run-plan` (aliases: `run-implementation-plan`, `execute-plan`, …). There is no separate implementer skill — plan, then run the plan.

---

## Plans directory (agent-specific)

Resolve `<plans-dir>` once at the start of this skill from the agent you are running as:

| Agent | `<plans-dir>` |
|-------|----------------|
| **Cursor** (Cursor IDE, Composer, Auto) | `../../plans` |
| **Claude** (Claude Code) | `../../plans` |

- Detect from the current runtime only — do **not** write to both directories.
- Output path is always: `<plans-dir>/<ISSUE-KEY>.md`
- Resolve paths relative to this skill file; report the absolute expanded path to the user (e.g. from `../../plans/NTF-1224.md`).
- Do **not** use the workspace `.tasks/` folder for new specs (legacy location; ignore unless the user points at an existing file there).

---

## Step 1 — Extract the Issue Key

Resolve `<TASK-ID>` / `<ISSUE-KEY>` per `../../kb/implementation/How-to-resolve-task-context.md` (message key/URL → branch → worktree folder → ask once). Do not ask for full paths to PRD or plans when convention files exist.

---

## Step 2 — Offline copy (required before planning)

**Source of truth for this skill** is the offline export at:

```text
../../prds/<ISSUE-KEY>.md
```

1. Check whether that file exists (e.g. `ls ../../prds/<ISSUE-KEY>.md`).
2. **If it exists** — use it. Do **not** re-download unless the user explicitly asks for a newer version.
3. **If it is missing** — run the `download-jira-task` skill **as a nested prerequisite** before continuing:
   - Read and follow `../download-jira-task/SKILL.md` for this issue key.
   - State clearly in your reasoning/actions: `called_from: plan-implementation` (so `download-jira-task` **skips** its cascade prompt into this skill).
   - Wait until `../../prds/<ISSUE-KEY>.md` exists, then continue.
4. **Read the offline file in sections** (token budget):
   - Always: title/summary metadata, `## Description`, and any acceptance-criteria headings in the description
   - Read `## Comments` **only if** AC is missing/thin, open questions remain, or you are in validate/fix-plan mode and the draft plan cites comments
   - Prefer Grep for criteria keywords over dumping the whole comments thread
   - When comments are read: keep comment **ids**; ignore bot/CI noise (see 3a)

Do **not** call Atlassian MCP for issue/comment fetch in this skill when the offline file is available (or was just created by the nested download). Live MCP fetch belongs in `download-jira-task` only. Do **not** read `*-evidence-plan.md` or sibling-task PRDs while drafting.

---

## Step 3 — Process offline data and classify

### 3a. Process comments (from the offline file)

Comments refine acceptance criteria — they are **not** dumped raw into the project spec (except absorbed intent):

- Ignore automated CI/CD, deploy bot, and status-change comments (author name contains "Bot", "GitLab", "GitHub", "Jenkins", "Bamboo", or similar)
- Look for requirement changes, clarifications, or new conditions
- If a comment contradicts or extends the description, **treat the comment as authoritative** and update acceptance criteria
- Mark criteria inferred or updated from comments with `_(from comments)_`

### 3b. Classify the task type

Analyze the issue title, description, and labels and pick **exactly one** category. This value goes in the `Type` field of the generated document and determines which reference file to load.

| Category | When to use | Reference file |
|---|---|---|
| **New Component** | Task creates a brand-new component, part, layout, macro, or page template | `references/new-component.md` |
| **Existing Component Change** | Task modifies, fixes, or extends a component that already exists in the project | `references/change-existing.md` |
| **API Integration** | Task involves connecting to or consuming an external/internal API, webhooks, data fetching, or service integration | `references/api-integration.md` |
| **Performance / Security** | Task focuses on optimizing performance or hardening security | `references/performance-security.md` |

If the task fits more than one category, pick the **primary** intent. If truly ambiguous, default to **Existing Component Change**.

**Load the matching reference file now** — you will need its guidance to fill the `Suggested Technical Approach` and `Implementation Steps` sections.

### 3c. Consult Enonic offline docs (when relevant)

If the task involves Enonic XP, CMS, platform APIs, or React4XP, **prefer offline LLM-dense docs** over live web fetches.

1. Pick the catalog row(s) that match the project/stack (XP 7 vs XP 8; React4XP 5.x legacy / 6.x / stable 7.x).
2. Open that catalog’s `llm-index.md` under `../../kb/offline-reference` and route to the matching page file(s).
3. Use those pages when drafting `Suggested Technical Approach` and `Implementation Steps`. Cite offline paths (e.g. `../../kb/offline-reference/xp8/docs/code/stable/libraries/lib-content.md`), not only URLs.
4. Skip this step only when the task is clearly unrelated to Enonic/React4XP.

| When | Skill | Routing index | Content root |
|------|-------|---------------|--------------|
| XP **7** backend (libs, controllers, framework, schemas) | `develop-xp7-backend` (`xp7-backend`) | `../../kb/offline-reference/xp7/llm-index.md` | `../../kb/offline-reference/xp7/{development,framework,api}/` |
| XP **8** / stable (platform, CMS, code kit) | `develop-xp8` (`xp8-docs`) | `../../kb/offline-reference/xp8/llm-index.md` | `../../kb/offline-reference/xp8/docs/{platform,cms,code}/stable/` |
| React4XP **5.x** (XP 7, legacy maintenance only) | `develop-react4xp-v5` (`react4xp-v5`) | `../../kb/offline-reference/react4xp-5.x/llm-index.md` | `../../kb/offline-reference/react4xp-5.x/learn/react4xp-tutorial/5.x` |
| React4XP **6.x** (XP 7, new React4XP work) | `develop-react4xp-v6` (`react4xp-v6`) | `../../kb/offline-reference/react4xp-6.x/llm-index.md` | `../../kb/offline-reference/react4xp-6.x/{learn/react4xp-tutorial,docs/react4xp}/6.x/` |
| React4XP **stable / 7.x** (XP 8 default) | `develop-react4xp-v7` (`react4xp-v7`) | `../../kb/offline-reference/react4xp-stable/llm-index.md` | `../../kb/offline-reference/react4xp-stable/{learn/react4xp-tutorial,docs/react4xp}/stable/` |

**Version hints:** XP 8 / `platform/stable` → XP8 + React4XP stable (7.x / `develop-react4xp-v7`). XP 7 new React4XP → React4XP 6.x (`develop-react4xp-v6`). XP 7 existing 5.x apps → React4XP 5.x maintenance only (`develop-react4xp-v5`). If unclear and the project already has React4XP files, infer from `package.json` / React4XP major or existing skill conventions; default to the version already used in the workspace.

### 3d. Check for a prototype component (New Component and Existing Component Change only)

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
5. This information is used in the Implementation Plan.

### 3e. Optional — Impeccable (design / frontend UI only)

**Skip by default.** Only consider when the task is clearly about **design or frontend UI** (visual layout, styling, UX copy on a surface, component presentation, landing/page look, responsive UI, motion, design-system tokens for a view). Skip for backend-only, API-only, CMS schema-only, infra, or non-UI refactors.

When it applies (optional, not mandatory):

1. Read the `impeccable` skill (`../impeccable/SKILL.md`) and run its session `context.mjs` if useful.
2. Prefer light planning cues over a full redesign: note which `/impeccable` commands fit later work (e.g. `shape`, `critique`, `audit`, `polish`, `typeset`, `layout`) and/or that `impeccable detect` can scan UI sources.
3. Fold at most a short **Design / UI (optional)** bullet into `Suggested Technical Approach` or `Definition of Done` — do not expand scope into a redesign unless the Jira task asks for it.

Do **not** block the spec on Impeccable, invent DESIGN.md/PRODUCT.md requirements the task does not need, or run detect across the whole repo “just in case.”

---

## Step 4 — Check if the plan / spec already exists

Check whether `<plans-dir>/<ISSUE-KEY>.md` already exists:

```bash
ls <plans-dir>/<ISSUE-KEY>.md 2>/dev/null
```

- **If it does not exist**: create the file from scratch using the template below
- **If it already exists**: read the current file, preserve the `## Implementation Plan` section if it has been manually edited by the user (check for content beyond the default template), and update the Jira-derived sections from the offline copy

Create the folder if needed:
```bash
mkdir -p <plans-dir>
```

---

## Step 5 — Generate the Markdown

Use the template below. Fill in all fields from the **offline copy** (and classification / prototype checks above).
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

<Fill using the reference file loaded in Step 4b. Follow its "Suggested Technical Approach — content to generate" section exactly.>

<If a prototype component was found in Step 4d, add a "Prototype Component" sub-section:>

**Prototype Component**: `<prototype-component-path>`

The frontend component already exists as a prototype. The Enonic view must render this component — do not create a duplicate React component.

<If <prototype-props-interface> was found:>

**Props contract**: The prototype file exports `<prototype-props-interface>`. This interface is the authoritative source for the props the processor must return. Do NOT generate a separate `*Props` interface in the Enonic `.d.ts` file — use or re-export the prototype interface instead, and remove any auto-generated `*Props` interface if it already exists.

<End prototype section>

### Implementation Steps

<Fill using the reference file loaded in Step 4b. Follow its "Implementation Steps — content to generate" section. Reference FR numbers where applicable.>

### Definition of Done

<Fill using the reference file loaded in Step 4b. Use its "Definition of Done checklist to include" section as the base, then add any criteria specific to this task's acceptance criteria.>

---

_Generated at: <current date and time in YYYY-MM-DD HH:MM format>_
_Source: [<ISSUE-KEY>](<full Jira issue URL>)_
_Offline copy: ../../prds/<ISSUE-KEY>.md_


```

---

## Step 6 — Save and confirm

1. Write the final content to `<plans-dir>/<ISSUE-KEY>.md`
2. Report to the user:
   - The absolute path of the generated file (and which agent plans dir was used)
   - Path of the offline copy used (`../../prds/<ISSUE-KEY>.md`)
   - A 1-2 line summary of what was found in the task
   - Whether the file was **created** or **updated**
   - Any data that was not found (e.g., no explicit acceptance criteria)
   - Whether any comments influenced the acceptance criteria

---

## Quality Notes

- **Offline first**: Prefer `../../prds/<ISSUE-KEY>.md`. Nested `download-jira-task` only when missing (or user asks for a refresh). Mark nested runs with `called_from: plan-implementation`.
- **Enonic offline docs**: For XP/React4XP work, route via Step 4c (`../../kb/offline-reference/…/llm-index.md` for XP7, XP8, React4XP v5, React4XP v6) before inventing API/framework details.
- **Language**: The generated Markdown file must always be in English, even if the Jira issue content or user messages are in another language. Translate descriptions, comments, and criteria as needed.
- **Comments drive criteria**: Comments are the most recent source of truth for requirements. Always process them before finalizing acceptance criteria. Do not surface raw comments in the output — absorb their intent into the criteria.
- **Inferred criteria**: When no explicit criteria exist, generate them from the description and clearly mark them with `_(inferred)_`.
- **User stories**: Break the task into small, specific stories. Each should represent one user-facing behavior. Avoid mega-stories that bundle multiple unrelated behaviors.
- **Functional requirements**: Extract explicit system behaviors from the description and criteria. Number them (FR-1, FR-2, ...) so implementation steps can reference them precisely.
- **Non-goals**: Always include at least one non-goal to clarify scope boundaries. Infer from context if not stated.
- **Implementation plan**: Be concrete and technical. Avoid vague statements like "implement the feature". Analyze the task context to suggest specific files, functions, or application layers likely to be affected.
- **Idempotency**: Running the skill twice on the same task should produce an equivalent file — do not duplicate sections or erase manual edits the user has made to the Implementation Plan.
- **Prototype component**: If a prototype file was found in Step 4d, the spec must instruct the implementer to use that file as the rendered component, not create a new one. The prototype file is the source of truth for the frontend implementation.
- **Prototype props interface**: If the prototype file exports a props interface, that interface is authoritative. The spec must explicitly state that any auto-generated `*Props` interface in the Enonic `.d.ts` should be removed or not created, and the prototype interface should be used (or re-exported) instead.
- **Impeccable (optional)**: Only for design/frontend UI tasks (Step 4e). Never required for general planning.
- **Auxiliary skills (optional)**: Use `find-skills` only for real capability gaps (not routine planning). Never invent session-only tooling when a quality skill exists.
