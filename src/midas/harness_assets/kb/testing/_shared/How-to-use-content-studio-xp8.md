# How to use Content Studio on XP 8 / CS 6

**Scope:** `_shared`  
**Applies to:** Enonic XP 8.x with Content Studio 6.x (verified on XP 8.0.3 / CS 6.0.3)  
**Related:** [How-to-search-via-datatoolbox.md](./How-to-search-via-datatoolbox.md)

## Prerequisites

- Logged-in XP admin session
- Content Studio admin tool URL (XP 8 — note **no** `/tool/` segment):

```
<base>/admin/com.enonic.app.contentstudio/main
```

Legacy `/admin/tool/com.enonic.app.contentstudio/main` returns 404 on XP 8.

### Agent login when no browser session (XP 8 idprovider)

Anonymous `/admin` is HTTP 401. Cold automation (e.g. Playwright without cookies) can obtain a session with:

```
POST <base>/admin/_/idprovider/system
Content-Type: application/json

{"action":"login","user":"<login>","password":"<password>"}
```

Success returns `{"authenticated":true,…}` and sets `JSESSIONID` (often also `INGRESSCOOKIE` behind ingress). Reuse those cookies for CS REST and authenticated browser navigation.

## Procedure

### Select project / layer

1. Open Content Studio. If prompted **Select project**, pick the CMS project that matches the site vhost (e.g. **English (en)** / `english`).
2. Browse URL shape: `#/<project>/browse` (e.g. `#/english/browse`).

### Create content

1. In the tree, select the **parent** (site or folder). New items are created under the current selection (`Create content in location: /…`).
2. Toolbar **New** (or `Alt+N`) → dialog with tabs **All / Suggested / Media**.
3. Type in the dialog **Search** field to filter types (e.g. `Landing`).
4. Click the type (e.g. **Landing page**). Content Studio opens the editor (often a **new browser tab**).

### Open existing content in the editor

Prefer direct navigation (avoids popup-blocker issues with toolbar **Edit**):

```
<base>/admin/com.enonic.app.contentstudio/main/<project>/edit/<content-id>
```

Example: `…/main/english/edit/54af2a2e-6240-4f32-a21c-aad9640d8227`

### Page editor + insert a Part

1. In the content editor, ensure the item is **renderable** (has a page controller or template). Collapse the content form if needed (**Collapse content form**) so the live page iframe is visible.
2. **Show Context Panel** → widget combobox (often shows **Details**) → **Toggle** → choose **Page** (“Draggable components and page controller”).
3. **Inspect** tab: set/select the page controller (e.g. app **Default**). Template **Automatic** locks editing — **Insert** stays disabled until the page is customized / uses a direct controller.
4. **Insert** tab: drag **Part** placeholder into a region (e.g. `main`), then pick the part from the dropdown (titles from YAML, e.g. Client Logo Bar).
5. Configure fields on **Inspect**; save.

> Agent note: the live page surface is an **iframe** (`…/admin/com.enonic.app.contentstudio/site/edit/<project>/draft/<site-path>`). Accessibility snapshots do not see inside it; use CDP `iframe.contentDocument` on same-origin or drive Insert from the outer **Page** widget.

### Fallback — insert / configure Part via CS REST (when UI drag fails)

Authenticated browser `fetch` (session cookies). Verified on XP 8 / CS 6 review (I99X-341):

```
POST /admin/rest-v2/cs/cms/<project>/content/content/page/update
Content-Type: application/json
```

Body shape (`CreatePageJson` known fields: `contentId`, `controller`, `template`, `config`, `fragment`, `regions`):

- `regions` must be an **array** (not a map): `{ name: 'main', components: […] }`
- Each component is a **typed wrapper**, e.g. `{ PartComponent: { descriptor, name?, config } }` (ids: `PartComponent`, `LayoutComponent`, `TextComponent`, `ImageComponent`, `FragmentComponent`)
- `config` is PropertyArray JSON: `{ name, type, values: [{ v }] }` — `Reference` uses `{ v: '<content-uuid>' }`
- **ItemSet** fields use `type: 'PropertySet'` with each occurrence as `{ set: [ /* nested PropertyArray entries */ ] }` (verified I99X-343 Expandable Link List `links`)

Rename / displayName (same session): `POST …/content/content/update` with `{ contentId, contentName, displayName, data, meta: [], requireValid: false }` (`contentName` renames the path segment).

Reload `/edit/<id>` (or draft site URL) after update. Draft preview without wizard:

```
<base>/admin/com.enonic.app.contentstudio/site/edit/<project>/draft/<site-path>/<page-name>
```

The `/site/preview/…` variant renders the same draft page **without** the editor chrome or iframe, so accessibility snapshots and DOM queries reach the page directly — prefer it for draft evidence (verified I99X-388):

```
<base>/admin/com.enonic.app.contentstudio/site/preview/<project>/draft/<site-path>/<page-name>
```

List content: `POST …/content/content/query` with `{ queryExpr, contentTypeNames: ['media:image'|'portal:site'|…], from, size }` → `{ contents: [{ id }] }`. Get one: `GET …/content/content?id=<uuid>` (only `id` works — `?path=` / `?contentPath=` return 500).

**Finding content you just created (draft-only):** the `queryExpr` form does **not** return
unpublished items, so a freshly created draft looks like it failed even when `create` returned 200.
Use the shape Content Studio's own search sends (verified I99X-388):

```json
POST …/content/content/query
{"from":0,"size":5,"contentTypeNames":[],"expand":"summary","aggregationQueries":[],"queryFilters":[],
 "query":{"boolean":{"should":[{"fulltext":{"fields":["displayName^5","_name^3","_allText"],
 "query":"delete-me-i99x-388","operator":"AND"}}]}}}
```

Create: `POST …/content/content/create` with `{ contentType, parent, name, displayName, data, meta: [], requireValid: false }` — `parent` is a **content path** (`/99x/Insights/blog`), `displayName` is mandatory (500 `displayName cannot be null` otherwise), and re-posting an existing name returns a 500 that names the branch (`… in branch [draft] already exists`) — a useful existence check.

**Nested layout + parts in one `page/update`:** a `LayoutComponent` carries its own `regions`, so the whole page tree goes in a single call:

```json
{"contentId":"<uuid>","controller":"no.seeds.99x:default","config":[],
 "regions":[{"name":"main","components":[
   {"LayoutComponent":{"descriptor":"<app>:article","name":"article","config":[],
     "regions":[{"name":"main","components":[{"PartComponent":{"descriptor":"<app>:list-people","config":[…]}}]}]}}]}]}
```

### Preview (draft)

- Toolbar **Preview** opens a full-tab draft render (subject to popup blocker).
- Prefer the draft site URL above or the in-editor iframe when Preview is blocked.

### Publish → live

1. Toolbar **Mark as ready** and/or **Publish** / **Publish tree** → Publishing wizard → **Publish Now**.
2. Only **master** is visible on public vhosts. After edits, status becomes **Modified** until re-published.

**REST fallback** (same auth session) when the wizard is awkward under automation:

1. `POST …/content/content/markAsReady` body `{ contentIds: ['<uuid>'] }` → 204  
2. Optional: `POST …/content/content/updateWorkflow` body `{ contentId, workflow: { state: 'READY', checks: {} } }`  
3. `POST …/content/content/publish` body `{ ids: ['<page-uuid>', '<dep-uuid>…'], excludedIds: [], excludeChildrenIds: [] }` → `{ taskId }`  
4. Poll `GET /admin/rest-v2/cs/tasks/<taskId>` until `progress.info` has `"state":"SUCCESS"`.

## Pitfalls

- **Popup blocker:** Edit / Preview / New often open a second tab. Prefer direct `/edit/<id>` URLs. Dismiss CS’s “Pop-up Blocker is enabled…” toast when it appears. Capture draft evidence from the in-editor iframe if Preview is blocked.
- **Insert disabled:** page still on automatic template without Customize / without choosing a controller. **Customize Page** (or pick controller **Default**) unlocks Insert.
- **Part drag under automation:** HTML5 / tool drag onto the region often does not stick; use the page/update REST fallback above, then reload the editor.
- **Inspect stuck on page Template after REST insert:** Components-tree clicks alone often leave Inspect on **Template / Default**. Click the part inside the draft iframe (`[data-portal-component-type=part]`), then **Expand content form** (or Collapse→Expand) so Inspect switches to the Part form (Overline / ItemSet fields).
- **Wrong project:** English vs Norwegian layers; public vhost must match the project you published in.
- Do not confuse emulator/preview-mode menus (**Automatic / Media / Standard / JSON**) with the **Page** context widget.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| CS URL | `http://localhost:8080/admin/com.enonic.app.contentstudio/main` |
| Project | `english` |
| Edit URL | `http://localhost:8080/admin/com.enonic.app.contentstudio/main/english/edit/<uuid>` |
