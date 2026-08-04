# Reference — Task Evidence Plan

Detailed recipes for URL derivation, authentication realms, timeouts, and the browser MCP.
Read this from `SKILL.md` only when you need the specifics.

---

## Enonic data-toolbox component lookups

The data-toolbox admin tool lets you query the content repo to find **where a component is
used**, so you can build a real page URL to screenshot.

**Tool URL** (needs `/admin` auth):

```
<base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox
```

**Search fragment** (NoQL-style `query` is URL-encoded after `#search?`):

```
#search?query=<URL-ENCODED NoQL>&sort=_score%20DESC
```

### Common queries (decode for readability)

| Goal | NoQL query (before encoding) |
|------|------------------------------|
| Pages using a **part** | `components.part.descriptor LIKE '*:two-columns-content'` |
| Pages using a **layout** | `components.layout.descriptor LIKE '*:my-layout'` |
| Pages using a **page** controller | `components.page.descriptor LIKE '*:my-page'` |
| Content of a **type** | `type = 'com.enonic.app.myapp:my-content-type'` |
| Text occurrence | `_allText LIKE '*some text*'` |

Encoding notes: space → `%20`, `:` → `%3A`, `'` stays `'`, `*` stays `*`. Example for the part
`two-columns-content`:

```
<base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox#search?query=components.part.descriptor%20LIKE%20'*%3Atwo-columns-content'&sort=_score%20DESC
```

### From a match to a page URL

A result row gives the content `_path` (e.g. `/site/en/tours/norway`). Build the live URL:

- Site page: `<base>/<site-path-without-/content-root>` — confirm the exact prefix on the env
  (often the path after `/<site-name>`), then verify by navigating.
- Content Studio edit view: `<base>/admin/tool/com.enonic.app.contentstudio/main/<branch>/edit/<contentId>`

When unsure of the public route, open the content in Content Studio and use its **Preview** to
get the canonical URL.

---

## Authentication realms

| Realm | Triggers | Default mode | Notes |
|-------|----------|--------------|-------|
| App login | `/minside`, `/min-side`, `/user`, `/profile`, "My Page" | User fills | Often SSO/social login |
| XP admin / Content Studio | `/admin`, data-toolbox | User fills | Admin session reused across tools |
| GitLab web | `git.seeds.no/...` screenshots | User fills | git CLI uses ssh-agent; **web UI still needs login** |
| External system | Tourplan, Ticketco, etc. | User fills | May be unreachable from the agent → mark impossible |

**Modes** (see plan **Authentication map** / skill Phase 4):
- *Agent fills* — user gives credentials to the agent; agent types them into the form.
- *User fills* — agent asks the user to log in; agent resumes on an authenticated session.

Always prefer *User fills* for sensitive realms. During plan **Execution**, **wait** until
the realm is ready before capturing — do not screenshot a login wall as "evidence".

---

## Timeouts (budgets)

Pick per operation; don't reuse one global value.

| Operation | Budget | Poll/verify |
|-----------|--------|-------------|
| Page load (local/review) | 10–15 s | `browser_snapshot` for the target element |
| Page load (cold/remote env) | 30 s | retry once before failing |
| API request (`curl`) | 10 s | check status + body shape |
| Remote/3rd-party service | 30–60 s | longer; flag flakiness |
| Task/job execution (XP task, build) | 60–300 s | poll status, don't block blindly |
| Auth wait (user logs in) | until ready | ask, then re-check session |

Prefer short polling loops (snapshot / CDP `Runtime.evaluate`) over a single long sleep.

---

## Browser MCP preference order

Unless the user names a different tool, select in this order:

| Rank | Namespace | Notes |
|------|-----------|--------|
| 1 | `cursor-ide-browser` | Cursor-owned browser; preferred for evidence (shared `/admin` session) |
| 2 | `user-browser-control` | External browser tab control |
| 3 | `user-playwright` | Separate Playwright process; cold cookies |

**Do not** infer that rank 1 is missing from `GetDynamicTools` pattern search alone.
Always call `GetDynamicTools` with `namespace: "cursor-ide-browser"` before falling back.

## Browser MCP cheatsheet (`cursor-ide-browser`)

| Need | Tool |
|------|------|
| List/inspect tabs | `browser_tabs` (action `list`) |
| Open/navigate | `browser_navigate` (omit `position` for background) |
| Lock before long run / unlock after | `browser_lock` |
| Read structure for actions | `browser_snapshot` |
| Capture image | `browser_take_screenshot` (`filename`, `fullPage`, `element`+`ref`) |
| Click / type / fill | `browser_click`, `browser_type`, `browser_fill` |
| Dropdowns / keys / scroll | `browser_select_option`, `browser_press_key`, `browser_scroll` |
| Inspect / evaluate JS / profile | `browser_cdp` (e.g. `Runtime.evaluate`) |

Rules: `browser_navigate` must create the tab **before** `browser_lock`. Do not use CDP
`Input.*`. Iframe content is not accessible. After a few failed attempts on a step, stop and
report the blocker.

### Screenshot storage and Jira upload

Save to `../../prds/<ISSUE-KEY>/evidence` with ordered, descriptive names
(`01-...png`, `02-...png`).

### Screenshot consistency (mandatory when posting to Jira)

If screenshots are **meant to post on Jira** (immediate evidence upload/comment), validate
each shot for consistency **before** `mogrify` / upload / comment:

| Check | Pass when |
|-------|-----------|
| Correct **element** | Intended target from the step is what’s shown (not wrong panel/sibling/modal) |
| Correct **zoom** | Scale/crop matches the step — subject readable and dominant as planned |
| Correct **example page** | Env, URL/path, locale, and sample content match the planned example |

**How:** Read the PNG with the Read tool (vision) and compare to the step’s goal / URL /
expected result. Retake until all three pass. Never upload or embed a failed shot.

If screenshots are **just for storage** (not for Jira evidence immediate post), validation
is **not** mandatory.

After all screenshots for an issue are captured (and Jira-bound shots validated), flatten
transparency and add a light gray border (browser shots often have alpha; the border
separates them from Jira’s white page):

```bash
cd ../../prds/<ISSUE-KEY>/evidence
mogrify -background white -alpha remove -bordercolor "#dddedd" -border 2x2 *.png
# repeat in before/ and after/ if those subfolders exist
```

One-pass ImageMagick `mogrify` (in-place) is preferred over a separate `convert … -border …`
to a new filename. If you must use `convert`, keep the same flags and overwrite the original
basename so upload paths stay unchanged.

**Then upload immediately** via Atlassian MCP preview (`user-atlassian-rovo-preview`):

1. Resolve `cloudId` once (`getAccessibleAtlassianResources` or pass the Jira site URL).
2. For each flattened PNG, `execute` with `name: "uploadAttachmentToJiraIssue"`:
   - **Phase A** — `inputs`: `{ issueIdOrKey, filePath }` → response includes a local
     `uploadCommand`. Run that command in the shell; capture the returned `fileId`
     (JSON `data.id` — media UUID).
   - **Phase B** — `inputs`: `{ issueIdOrKey, fileId }` → attaches the file to the issue.
3. Track `{ basename, fileId, uploaded }` for every file. On failure: one corrected retry, then
   stop further uploads; use `[Attachment: <basename>]` placeholders in the evidence comment
   **only for files that did not attach**. Do not invent other upload paths. Report upload
   success/failure in **chat only** (never in the Jira comment body).

### Evidence comment: ADF media embeds (mandatory when upload succeeded)

Do **not** put `[Attachment: filename.png]` in the comment for an uploaded file — that is
plain text and does not show the image. Post the comment with `contentFormat: "adf"` and, for
each successful upload, insert a `mediaSingle` under the step explanation:

```json
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
        "alt": "01-example.png",
        "width": 900,
        "height": 560
      }
    }
  ]
}
```

- `attrs.id` **must** be the Phase A media `fileId` from the upload JSON (not the numeric
  Jira attachment id).
- Prefer `addCommentToJiraIssue` / `addOrEditJiraIssueComment` with `contentFormat: "adf"` and
  `commentBody` set to the full ADF document JSON string.
- Avoid markdown `![…](attachment-url)` and wiki `!file|thumbnail!` for this flow — they often
  become broken external blobs.

Text `[Attachment: <basename>]` is **fallback only** when that file never uploaded. Full ADF
shape is in [templates.md](templates.md).
---

## curl evidence (non-UI)

For backend-only checks, a request tool is enough and needs no scope warning:

```bash
curl -sS -D - -o /dev/null "<base>/service/<app>/<service>"      # status + headers
curl -sS -I "<base>/path/to/file.pdf"                             # verify content-type
```

Capture the command + output into the plan/comment as text evidence (no screenshot needed).
