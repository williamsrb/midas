# Templates — Task Evidence Plan

Two templates: the **Evidence Creation Plan** (written by `plan-task-evidence`;
includes an **Execution** section for later runs) and the **Jira evidence comment**
(used when executing the plan). Fill placeholders in `<...>`; keep section structure.

---

## Evidence Creation Plan

Save to `../../plans/<ISSUE-KEY>-evidence-plan.md`.

**Required:** include the **Execution** section below in every generated plan file.
`plan-task-evidence` stops after writing this file; capture / Jira / KB steps run
only when someone later follows that Execution section (e.g. `run-plan`).

```markdown
# Evidence Plan — <ISSUE-KEY>: <summary>

**Jira:** https://seeds.atlassian.net/browse/<ISSUE-KEY>
**Testing base URL:** <base>
**Change type:** <user-visible | user-transparent | mixed>
**Evidence folder:** ../../prds/<ISSUE-KEY>/evidence
**Status:** planned — do not execute until explicitly approved

## Acceptance criteria
1. <concrete pass/fail criterion>
2. <...>

## Scope warning
<Only if evidence crosses frontend↔backend or a boundary. Name the layers and say it needs
end-to-end verification. Otherwise: "Single scope — no cross-scope warning.">

## Testing tips (from description/comments)
- <tip + source comment id, e.g. "URL X fails on direct access; open via Y first — comment 511700">

## Sources
<!-- Testing KB = instrumentation. Offline reference = product/API semantics. -->
- **Testing KB:** <`../../kb/testing/.../How-to-….md` | none — gap for KB write-back on execute>
- **Offline reference:** <e.g. `../../kb/offline-reference/content-studio-stable/docs/content-studio/stable/actions/new.md` | n/a>

## Authentication map
| Realm | Steps | Mode | Status |
|-------|-------|------|--------|
| <app login / admin / gitlab / external> | <step #s> | <agent fills / user fills> | <pending/ready> |

## Steps
<!-- Goal = what the screenshot will prove toward a requirement/AC (feeds the Jira comment
     explanation). Never plan a shot that would land in the comment without that prose. -->
| # | Goal (what it proves) | URL | Auth | Timeout | Expected result | Screenshot file |
|---|------|-----|------|---------|-----------------|-----------------|
| 1 | <ties to AC #…; what analyst should see> | <url> | <y/n realm> | <budget> | <expected> | 01-<name>.png |
| 2 | ... | ... | ... | ... | ... | 02-<name>.png |

## Cut / impossible (with reason)
- <step> — <cut: proves nothing | impossible: agent can't reach / can't upload>

---

## Execution (run only after explicit approval)

> **Gate:** Do not start this section until the user explicitly says to execute
> (e.g. "go", "execute", "run the plan"). Planning alone is not approval.
> Prerequisites: ImageMagick (`mogrify`), browser MCP, Atlassian MCP for uploads.
> Detail recipes: `~/.cursor/skills/plan-task-evidence/reference.md` and
> `~/.cursor/skills/plan-task-evidence/templates.md` (Jira comment / ADF).

### E1 — Capture

1. Re-check docs if CMS/UI semantics stall: matching `offline-reference` pages and
   testing How-Tos under `../../kb/testing/_shared` and `../../kb/testing/<project>`.
   Persist new stable site-specific steps in E3 (testing KB only).
2. Browser MCP order (unless user names a tool): `cursor-ide-browser` →
   `user-browser-control` → `user-playwright`. Probe
   `GetDynamicTools` `{ "namespace": "cursor-ide-browser" }` before falling back.
   Record which MCP was used in the chat report.
3. With `cursor-ide-browser`: lock before a long sequence; unlock when done.
4. For each row in **Steps**:
   1. `browser_navigate` to the URL (omit `position` for background automation).
   2. Authenticate per **Authentication map** if the realm is not ready.
   3. `browser_snapshot` to confirm expected state.
   4. `browser_take_screenshot` with explicit `filename` into
      `../../prds/<ISSUE-KEY>/evidence` (e.g. `01-<name>.png`).
      Copy from `/tmp/cursor/screenshots/…` into the evidence folder when needed.
   5. **Jira-bound consistency check (mandatory before upload/post):** Read the
      image and confirm **correct element**, **correct zoom**, and **correct
      example page** vs this step. Retake on failure — do not flatten/upload a
      bad shot. (Storage-only captures with no immediate Jira post: check optional.)
   6. Record the local path for each validated shot.
5. After all captures (including `before/` / `after/` if used), from the evidence folder:
   ```bash
   mogrify -background white -alpha remove -bordercolor "#dddedd" -border 2x2 *.png
   ```
6. **Upload** each flattened PNG via Atlassian MCP preview
   (`user-atlassian-rovo-preview` → `uploadAttachmentToJiraIssue`):
   - Phase A: `filePath` → run returned `uploadCommand` → keep `fileId` (media UUID).
   - Phase B: `fileId` → attach to `<ISSUE-KEY>`.
   - Resolve `cloudId` once. Track `{ basename, fileId, uploaded }`.
   - On failure after one corrected retry: stop further uploads; use text
     `[Attachment: <basename>]` in E2 **only** for files that did not attach.
7. If a step fails: fresh snapshot; after a few attempts, stop and report the
   blocker — do not loop.

### E2 — Jira evidence comment

**Audience: analyst/reporter only.** No local paths, upload how-tos, or
evidence-machine logistics in the Jira body.

- Every screenshot must sit under an explanation of **what it proves** (AC).
  Never orphan images or dump a gallery at the end.
- Prefer ADF (`contentFormat: "adf"`) with `mediaSingle` / `media` using Phase A
  `fileId` for each successful upload. Never `[Attachment: …]` for an uploaded file.
- Placeholder `[Attachment: <basename>]` only when that file failed to upload.
- Build the comment from the **Jira evidence comment** template in
  `~/.cursor/skills/plan-task-evidence/templates.md`.
- Post with `addCommentToJiraIssue` / `addOrEditJiraIssueComment`. Mention the
  analyst via `lookupJiraAccountId` when named.
- **Chat report-back (not Jira):** issue link, comment id, upload vs placeholder,
  local evidence folder, KB files from E3, manual follow-ups.

### E3 — Testing-KB write-back (when know-how was gained)

After E1/E2, if this run taught reusable how-to knowledge (and it was not already
fully covered by existing How-Tos):

1. Scope: `_shared` for Enonic/CMS/datatoolbox; `<project>` for app-specific flows.
2. Create/update the smallest set of `How-to-*.md` under `../../kb/testing/…`
   (merge when topic fits; split when mixing concerns). Format: `kb-format.md`.
3. Procedure + stable selectors only — no screenshot dumps or Jira comment text.
4. Optional short **Sample data** (minimum examples). Report files touched in chat.
```

---

## Jira evidence comment

Post with `addCommentToJiraIssue` or preview `addOrEditJiraIssueComment`. Prefer
`contentFormat: "adf"` whenever any screenshot uploaded successfully. Use real mentions for
people (ADF `mention` node).

**Audience: analyst/reporter.** Write only what helps them validate the change. Do **not**
include local paths, upload/attach how-tos, or any evidence-generation / developer logistics.

**Purpose of each evidence unit:** convince the analyst that the solution fulfills the
requirements and meets the acceptance criteria. A screenshot without explanation has **no
meaning** — never post one.

**Attachments (placement rules):**
- **Uploaded (required when E1 upload succeeded):** embed each image with ADF `mediaSingle` /
  `media` using the Phase A media `fileId`. Place it **immediately under** that step's
  explanation.
- **Upload failed only:** `[Attachment: <basename>.png]` under the explanation.
- **Do not** use `[Attachment: …]` for a file that uploaded, and do **not** gather screenshots
  in a gallery at the end of the comment.
- Never put local paths or "please attach" instructions in the comment.

### Preferred: ADF body (uploads succeeded)

Build one ADF `doc`. For each evidence step: a `paragraph` (explanation), then a
`mediaSingle` whose child `media` uses the upload `fileId`:

```json
{
  "type": "doc",
  "version": 1,
  "content": [
    {
      "type": "paragraph",
      "content": [
        { "type": "mention", "attrs": { "id": "<accountId>", "text": "@Analyst Name" } },
        { "type": "text", "text": " — evidence for <ISSUE-KEY>." }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 3 },
      "content": [{ "type": "text", "text": "Changes summary" }]
    },
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "<High-level description of what was implemented.>" }]
    },
    {
      "type": "heading",
      "attrs": { "level": 3 },
      "content": [{ "type": "text", "text": "Deployed testing environment" }]
    },
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "<https://review.example/ — deployed URL only>" }]
    },
    {
      "type": "heading",
      "attrs": { "level": 3 },
      "content": [{ "type": "text", "text": "Evidence" }]
    },
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "1. <What was verified / which AC; what to look for in the image.>" }]
    },
    {
      "type": "mediaSingle",
      "attrs": { "layout": "wide" },
      "content": [
        {
          "type": "media",
          "attrs": {
            "type": "file",
            "id": "<Phase-A-fileId-UUID>",
            "collection": "",
            "alt": "01-<name>.png",
            "width": 900,
            "height": 560
          }
        }
      ]
    },
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "2. <Next evidence unit explanation.>" }]
    },
    {
      "type": "mediaSingle",
      "attrs": { "layout": "wide" },
      "content": [
        {
          "type": "media",
          "attrs": {
            "type": "file",
            "id": "<Phase-A-fileId-UUID>",
            "collection": "",
            "alt": "02-<name>.png",
            "width": 900,
            "height": 560
          }
        }
      ]
    },
    {
      "type": "heading",
      "attrs": { "level": 3 },
      "content": [{ "type": "text", "text": "Acceptance criteria" }]
    },
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "<met / partially met — map each AC to evidence # above>" }]
    }
  ]
}
```

Pass that JSON as `commentBody` with `contentFormat: "adf"`.

### Fallback only: markdown placeholders (uploads failed)

```markdown
<@Analyst Name> — evidence for <ISSUE-KEY>.

**Changes summary**
<High-level description of what was implemented. No low-level technical detail.>

**Deployed testing environment**
<Deployed/review testing URL only, e.g. https://review.as.k8s.seeds.no/ — never localhost or machine paths>

**Evidence**

1. <What was verified and which requirement / AC it satisfies. Tell the analyst what to look
   for in the screenshot (e.g. field X shows Y on page Z).>
   [Attachment: 01-<name>.png]

2. <Same pattern: explanation that gives the image meaning, then the placeholder under it.>
   [Attachment: 02-<name>.png]

Optional text evidence (e.g. curl output) — same rule: short meaning first, then the block:
$ curl -sS -I <url> → HTTP/2 200, content-type: application/pdf

**Acceptance criteria:** <met / partially met — note any gaps; map each AC to the evidence # above>

**Additional relevant details (optional)**
<Analyst-facing only: known product limitation, how to reproduce on the deployed URL, fallback UX.
Never: local folders, attach instructions, agent/auth setup, KB/plan paths.>
```

### Notes
- **Explanation + image stay together** as one unit. Never orphan a screenshot (no
  description) and never dump all images at the bottom after the prose.
- Each explanation must state **what the image proves** toward requirements / ACs — not just
  a vague step title.
- `media.attrs.alt` and placeholder labels use the **basename** only (`01-foo.png`), never a
  directory path.
- **Never** post in Jira: `../.....`, `/home/...`, evidence-folder paths, "please attach
  from …", mogrify/upload steps, or other developer/evidence-machine instructions. Put those
  in the chat report-back only.
- Keep `alt` / placeholder basenames identical to the uploaded (or local) filenames.
- **Placeholder fallback only:** after the user attaches the missing files (coordinated in
  chat), edit the same comment (`commentId`) and replace each `[Attachment: ...]` with an ADF
  `mediaSingle` using the new Phase A `fileId` — still keeping each image under its explanation.
- If no analyst is named, drop the mention line; otherwise resolve the account with
  `lookupJiraAccountId` so the mention renders as an entity, not plain text.
