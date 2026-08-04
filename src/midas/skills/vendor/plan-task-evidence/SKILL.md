---
name: plan-task-evidence
aliases: task-evidence-plan, evidence-plan, jira-evidence, evidence-creation-plan
description: >-
  **Planning only.** Ultimate deliverable: write
  `../../plans/<ISSUE-KEY>-evidence-plan.md` for a Jira issue, then hard-stop
  for user approval. Collects description, comments and related tasks,
  **always scans the knowledge base** (`../../kb/testing`) for instrumentation
  How-To guides, and **consults offline API/UI docs** (`../../kb/offline-reference`)
  when evidence needs CMS or platform semantics (Content Studio create/edit/publish,
  XP libs, React4XP), derives test URLs (incl. Enonic data-toolbox component
  lookups), and maps required authentication. Injects an **Execution** section
  into the plan file (capture, Jira comment, KB write-back) — those steps are
  **not** run by this skill. The plan file **must** exist on disk before the
  hard-stop; a chat-only summary is not success. Use when the user asks to
  create an evidence plan, plan QA/test evidence, or document how verification
  will work for a Jira issue — typically given a task ID (e.g. RFD-123) and a
  testing base URL (e.g. https://review.as.k8s.seeds.no/).
---

# Task Evidence Plan

**Ultimate goal:** create (or update) the Evidence Creation Plan file at
`../../plans/<ISSUE-KEY>-evidence-plan.md`. That file is the success criterion
for this skill. Chat summaries are secondary; **never** hard-stop or claim
planning is done without that file on disk.

**This skill plans only.** It collects context, writes/refines the plan file
(including an **Execution** section for later use), maps auth, then stops.
It does **not** open browsers, take screenshots, upload to Jira, post comments,
or write testing-KB How-Tos. Those steps live **inside the generated plan file**;
run them later via `run-plan` / explicit approval by following that file’s Execution section.

Do **not** call SwitchMode or ask to switch to Plan mode. Write the plan file in the current mode, then hard-stop.

## Context budget (token)

1. Resolve `<TASK-ID>` via `../../kb/implementation/How-to-resolve-task-context.md`
2. Open **only** the allowlisted paths for this skill (see that How-to)
3. Prefer Grep / section reads over whole-file reads
4. If the user @-attached extra harness MDs outside the allowlist, ignore unless they explicitly override
5. Never ask the user to paste paths to PRD / impl plan / evidence plan when convention files exist
6. Prefer AC from `../../plans/<TASK-ID>.md`; use sectioned PRD only for tips/URLs/comment ids when the impl plan lacks them. Do **not** re-read full impl narrative or full PRD comments “just in case”
7. Validate-evidence mode: read `../../plans/<TASK-ID>-evidence-plan.md` + the AC source used in the draft — not the full impl plan / full PRD

### Cursor IDE

**Always** persist the plan with **Write** / **StrReplace** to
`../../plans/<ISSUE-KEY>-evidence-plan.md` (create `../../plans` with Shell
`mkdir -p` if needed). Planning must not open browsers or post to Jira.

## Two doc sources (do not mix roles)

| Source | Path | Role | Write back? |
|--------|------|------|-------------|
| **Testing KB** | `../../kb/testing` | Project/site **instrumentation** — click paths, selectors, auth tips, datatoolbox queries | **Yes** (during plan *execution*, not this skill) |
| **Offline reference** | `../../kb/offline-reference` | Official **LLM-dense** product/API docs (Content Studio, XP, React4XP, …) | **No** — refresh via sync scripts only |

Prefer testing How-Tos for *how we automate this site*. Prefer offline-reference when the
flow depends on *how Content Studio / XP / React4XP actually works* (create content, publish
wizard, layers, page editor, rich text, permissions, lib APIs) and the How-To is missing or
thin. Catalog index: `../../kb/offline-reference/README.md`.

## Knowledge base — purpose and self-feed loop

The KB at `../../kb/testing` is **not** an evidence dump. It stores **how to perform
tasks** (instrumentation): UI steps, selectors, CMS navigation, auth realms, URL
patterns, and datatoolbox queries — so agents can run tests **by themselves** on
the next issue.

| Store in KB | Do **not** store in KB |
|-------------|------------------------|
| Repeatable procedure (ordered steps) | Full screenshot sets, Jira comment text |
| Stable selectors, field names, save/publish sequence | Large booking dumps, email bodies, audit tables |
| Minimal **sample data** (one example email, one tour slug, one date) | Every test run's IDs unless they illustrate a reusable pattern |
| Auth tips, blockers, "needs referer" notes | Task-specific acceptance-criteria prose |

**Folder layout:**

| Path | Content |
|------|---------|
| `../../kb/testing/_shared` | Cross-project instrumentation (e.g. Enonic Content Studio, datatoolbox) |
| `../../kb/testing/<project>` | Project-specific flows (`as` for Authentic Scandinavia) |

**File naming:** `How-to-<verb>-<object>.md` (e.g. `How-to-search-via-datatoolbox.md`,
`How-to-start-booking-from-tour.md`). Link related guides; split when a file grows
past one concern.

**Sample data rule:** one short **Sample data** section at the end — only values
needed to execute the procedure (e.g. review base URL, one bookable tour slug, one
test email). Never the focus of the document.

See [kb-format.md](kb-format.md) for the How-To template. KB write-back instructions
belong in the plan file’s **Execution** section (filled from [templates.md](templates.md)).

## Auxiliary skills (optional, on demand)

Not required for every run. When planning needs a specialized capability you cannot perform
with already-installed skills / MCP / normal tools, and a session-only script is not worth it:

1. Prefer an already-installed skill if one covers the need.
2. Otherwise follow the `find-skills` skill as a nested prerequisite (`called_from: plan-task-evidence`): search, verify quality, install if appropriate, then **read and follow** the new skill for the blocked action.
3. Resume this skill’s planning workflow after the gap is closed.

Example: the issue references a `.fig` / Figma file and no Figma reader is installed →
`find-skills` → install/use a reader → continue drafting the plan.

## Inputs

| Input | Required | Example |
|-------|----------|---------|
| Jira task ID | yes | `RFD-123`, `AS-1171` |
| Testing base URL | yes | `https://review.as.k8s.seeds.no/` |

If either is missing, ask for it before continuing. Derive any other URL from the base
URL — never hardcode a different host than the one the user gave.

## Workflow

```
- [ ] Phase 1: Collect (offline task copy, **testing KB scan**, **offline-reference when needed**, related tasks, lookups)
- [ ] Phase 2: **Write** `../../plans/<ISSUE-KEY>-evidence-plan.md` from [templates.md](templates.md) — includes Steps **and** Execution section
- [ ] Phase 3: Evaluate & **rewrite the plan file** on disk
- [ ] Phase 4: Map authentication into the plan file
- [ ] STOP: confirm plan file exists; present path + auth map; ask whether to execute later. Do not run the Execution section.
```

### Hard stop (mandatory)

**Precondition:** `../../plans/<ISSUE-KEY>-evidence-plan.md` **must already exist**
(written in Phase 2, updated through Phase 3/4). If it does not, go back and write
it — do not hard-stop with only a chat outline.

After Phase 3/4:

1. Confirm the plan file is on disk; present its path, the step list, auth map,
   and any scope warnings.
2. **Ask** whether the user wants to execute later (e.g. via `run-plan` or an
   explicit “execute / go / run the plan”). Do **not** start the plan’s Execution
   section from this skill.
3. Staying in the current mode is **not** permission to execute. Silence or
   answering only planning questions is **not** a go-ahead.
4. If the user only wanted the plan, end here — success is the written plan file.
5. If the user explicitly approves execution in-thread, follow the **Execution**
   section **inside that plan file** (and [reference.md](reference.md) /
   [templates.md](templates.md) where the plan points) — do not re-derive capture
   rules from this skill body.

---

## Phase 1 — Collect

0. **Resolve `<TASK-ID>`** via `How-to-resolve-task-context.md` (message / branch / worktree). Do not ask for full paths when convention files exist.
1. **Acceptance criteria source (prefer plan).** If `../../plans/<TASK-ID>.md` exists, read its AC / requirements / validation block first. Only open `../../prds/<TASK-ID>.md` for tips, URLs, or comment ids the plan lacks — sectioned reads, not a full comments dump “just in case”.
2. **Offline task copy when needed.** If the PRD is missing and you still need Jira text, follow `download-jira-task` (keeps comment IDs). If `../../prds/<TASK-ID>.md` already exists, use it — only re-download when the user explicitly asks for a newer version.
3. **Testing KB scan (mandatory).** **Always** before drafting URLs or flows:
   - List `../../kb/testing/_shared` and `../../kb/testing/<project>` (`How-to-*.md`). Project slug
     is usually the Jira project key lowercased (`AS` → `as`).
   - Read every guide that matches what you will test (booking, CMS edit, datatoolbox lookup,
     payment gateway). **Reuse instrumentation verbatim** — do not rediscover selectors or
     Content Studio click paths the KB already documents.
   - Note in the evidence plan which KB file(s) were used (or **gaps** for KB write-back
     during later execution).
4. **Offline reference scan (when relevant).** After the testing KB scan, consult
   `../../kb/offline-reference` whenever evidence steps will use Enonic CMS UI or
   platform semantics — especially **creating, editing, publishing, or configuring content
   in Content Studio**, page editor / rich text / permissions / layers / issues, XP lib
   behavior, or React4XP edit-mode expectations. Prefer offline docs over live web fetches.
   1. Open `../../kb/offline-reference/README.md` and pick the **best-fit catalog(s)**
      (see table below).
   2. Read that catalog’s `llm-index.md`; match tokens to the evidence need (e.g. `publish`,
      `page editor`, `new`, `content form`, `layers`).
   3. Open only the matching page file(s); use them to draft CMS steps, expected UI labels,
      and auth/reachability notes. Cite paths in the plan **Sources** section.
   4. Skip this step only when the evidence plan is clearly unrelated (e.g. pure GitLab
      source screenshot, non-Enonic app login only).

   | Evidence need | Catalog | LLM index |
   |---------------|---------|-----------|
   | Content Studio UI on **XP 8** / CS 6.x | `content-studio-stable/` | `…/content-studio-stable/llm-index.md` |
   | Content Studio UI on **XP 7** / CS 5.x | `content-studio-5.x/` | `…/content-studio-5.x/llm-index.md` |
   | XP **7** APIs / framework (verify server behavior) | `xp7/` | `…/xp7/llm-index.md` |
   | XP **8** platform / CMS / code | `xp8/` | `…/xp8/llm-index.md` |
   | React4XP **5.x** (XP 7, legacy maintenance) | `react4xp-5.x/` | `…/react4xp-5.x/llm-index.md` |
   | React4XP **6.x** (XP 7, new React4XP work) | `react4xp-6.x/` | `…/react4xp-6.x/llm-index.md` |
   | React4XP **stable / 7.x** (XP 8 default) | `react4xp-stable/` | `…/react4xp-stable/llm-index.md` |

   **Version hints:** Infer from repo `xpVersion` / Gradle / React4XP major, or from the
   review host’s stack. XP 8 → Content Studio **stable** + React4XP **stable (7.x)** + `xp8`.
   XP 7 new React4XP → Content Studio **5.x** + React4XP **6.x** + `xp7`. XP 7 legacy 5.x
   apps → React4XP **5.x** maintenance only. If unclear and the task only needs Content
   Studio clicks, default to **stable** unless the project is known XP 7.
   When both a testing How-To and an offline page apply, **How-To wins for selectors/URLs**;
   offline docs win for product semantics (what Publish does, when Page editor appears, etc.).
5. **Related tasks.** Search for prior/sibling work on the same component or feature; their
   comments often contain the exact lookup query, test URL, or "this URL needs login" tip.
   - `searchJiraIssuesUsingJql` with terms from the summary, or follow issue links.
   - Reuse any **component lookup query** found verbatim (see Phase 2).
6. **Identify the change type** — it decides what evidence is needed:
   - **User-visible** (UI, copy, behavior) → app page screenshots.
   - **User-transparent** (removed comments, formatting, changed hard-coded value, refactor)
     → **GitLab source screenshots** are usually required (diff is the evidence).
7. **Optional — Impeccable (design / frontend UI only).** **Skip by default.** Only when the issue is clearly about **design or frontend presentation** (layout, styling, visual QA of a surface, UX polish) — not for backend, API, schema, or non-UI verification. When it applies, you may briefly consult the `impeccable` skill and/or run `impeccable detect` on the touched UI paths to decide if an evidence step should prove a design/a11y fix; do not add Impeccable steps for every UI ticket, invent redesign scope, or treat detect findings as required acceptance criteria unless the task already demands them.

---

## Phase 2 — Draft the Evidence Creation Plan

**Mandatory:** write the plan to `../../plans/<ISSUE-KEY>-evidence-plan.md` using
the full template in [templates.md](templates.md) — including the **Execution**
section. Use **Write** (create) or **StrReplace** (update). Create `../../plans`
if missing. This file is the skill’s ultimate deliverable — do not keep the plan
only in chat.

Copy the Execution block from the template into the plan file **as-is** (fill
`<ISSUE-KEY>` / paths). Do not omit it. That section is how a later `run-plan`
(or approved execute) knows what to do; it is not run during this skill.

Each evidence step has: goal, URL, auth needed (y/n), timeout, expected result,
screenshot file name.

Every planned screenshot must have a **goal that states what it proves** (requirement / AC).
If a step would only produce an unlabeled image, rewrite or cut it — evidence without meaning
is not evidence. At execute time, Jira-bound shots are consistency-checked (element, zoom,
example page) before upload; storage-only shots need not be.

### Deriving test URLs

- **Direct page**: combine the testing base URL with the path from the description/comments.
- **Enonic component usage** (find where a part/layout/page is used): use the data-toolbox
  lookup, then build the page URL from the matched content path. Lookup recipes and the URL
  shape are in [reference.md](reference.md). Example from a real task — a Part named
  `two-columns-content`:
  ```
  <base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox#search?query=components.part.descriptor%20LIKE%20'*%3Atwo-columns-content'&sort=_score%20DESC
  ```

### Source-code evidence (GitLab)

For user-transparent changes, plan a screenshot of the relevant file/diff in GitLab
(`https://git.seeds.no/seeds/<repo>/-/...`). Note: **git CLI auth is usually fine** (ssh-agent),
but the **GitLab web UI needs a logged-in browser session** — flag it as an auth step (Phase 4).

---

## Phase 3 — Evaluate & adjust the plan

Apply every check, then **rewrite the plan file on disk** (not only in chat). Keep the
**Execution** section intact (update issue-specific paths if needed).

- **Honor testing tips** from description/comments. Some URLs fail on direct access (need a
  referer, a prior navigation, or a session) — a comment often says so. Do not silently ignore it.
- **Map auth-gated steps** — any path under `/admin`, `/minside`, `/min-side`, `/user`,
  `/profile` (and the data-toolbox) needs authentication → route to Phase 4.
- **Define acceptance criteria** — if the task has none explicit, write concrete pass/fail
  criteria for each evidence step.
- **Define timeouts** — page load, API request, task execution, and remote services each get a
  different budget (see [reference.md](reference.md)).
- **Cut useless steps** — drop evidence that proves nothing for this change, and drop any
  screenshot that cannot be paired with a clear “what this proves” explanation.
- **Remove impossible steps** — anything that can't run from an agent (e.g. an account the
  agent can't reach). Note them as manual follow-ups. Screenshot upload is attempted during
  plan execution; do not treat it as impossible up front.

> WARNING — emit this when evidence spans more than one scope (e.g. a value set in the
> frontend that must appear in the backend, or a cookie crossing the boundary). State that it
> needs end-to-end verification, not a single-layer check, and name the layers involved.

### Reachability gate (mandatory — do not skip)

Before finalizing the plan file and moving to Phase 4, apply the following gate to
**every core evidence step** (steps that directly prove an acceptance criterion). A step
is **reachable** only when ALL of these are known or obtainable without user input at
execution time:

| Requirement | Examples of what is missing |
|-------------|-----------------------------|
| A concrete URL the agent can navigate to | feature hidden behind a search result, requires a specific record ID, or depends on post-deploy data that doesn't exist yet |
| Any required data to reach that URL | booking ref + last name, content ID, user account, specific CMS record |
| Auth realm is coverable in Phase 4 (user fills or agent fills with supplied credentials) | — |

**If any core step fails the gate:**

1. List every blocked step with the exact missing input (e.g. "booking ref + last name for a post-deploy booking with status `New`").
2. Use `AskQuestion` to ask the user for those inputs **before finalizing** the plan file
   or moving to the hard-stop.
3. **Do not** finalize an untestable skeleton as if it were ready to execute. If the user
   supplies the inputs, update the plan file with concrete URLs/data, then continue.
4. If the user cannot supply the missing inputs and the blocked steps cover all acceptance
   criteria, **still write** `../../plans/<ISSUE-KEY>-evidence-plan.md` (with Execution
   section) documenting the blocker and that execution cannot proceed, then hard-stop with
   that file as the deliverable: _"This task cannot be evidenced without [X]. Plan file records the gap."_

Only treat the plan as execution-ready when every core step has a reachable URL and all
blocking inputs are in hand — and that state is reflected in the plan file.

---

## Phase 4 — Map authentication → wait/ask

For each auth-gated step, list the **realm** (app login, `/admin` / Content Studio, GitLab web,
external system like Tourplan) and pick a mode:

- **Agent fills** — the user supplies credentials to the agent; the agent types them into the
  login form during automation. Use only when the user explicitly hands over credentials.
- **User fills** — the agent asks the user to log in themselves; the agent resumes once the
  browser session is authenticated (credentials already filled in the current session).

Default to **User fills** for anything sensitive (GitLab, SSO, `/admin`). Record the auth
map **in the plan file**, then present it as part of the **hard stop** (after the file
exists). Do **not** start logging in or navigating for capture from this skill.

---

## Companion files (for plan authors and later executors)

| File | Role |
|------|------|
| [templates.md](templates.md) | Plan body + **Execution** block to inject; Jira evidence comment / ADF shapes |
| [reference.md](reference.md) | Data-toolbox lookups, timeouts, browser MCP, upload Phase A/B |
| [kb-format.md](kb-format.md) | How-To template for testing-KB write-back during execution |

`plan-task-evidence` is the **primary** entry point for **planning** browser/CMS evidence.
The deliverable is `../../plans/<ISSUE-KEY>-evidence-plan.md`. Running that plan’s
Execution section is a separate step (`run-plan` or explicit user approval).
