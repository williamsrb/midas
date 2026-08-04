# How to create disposable part test content on i99x-group review

**Scope:** `i99x-group`  
**Applies to:** review host only (`https://review.i99x-group.k8s.seeds.no/`)  
**Related:** [_shared/How-to-use-content-studio-xp8.md](../_shared/How-to-use-content-studio-xp8.md), [How-to-verify-review-environment.md](./How-to-verify-review-environment.md), [How-to-test-parts-on-local-xp8.md](./How-to-test-parts-on-local-xp8.md) (study only)

## Purpose

Create **one-shot** CMS content used for Jira evidence screenshots. Content is **not** reused across runs. After evidence is posted, the human deletes it manually.

## Naming (mandatory — so it can be found and deleted)

| Field | Pattern | Example |
|-------|---------|---------|
| Display name | `DELETE-ME — <ISSUE-KEY> — <short label>` | `DELETE-ME — I99X-339 — Client Logo Bar` |
| Path name | `delete-me-<issue-key-lower>-<slug>` | `delete-me-i99x-339-client-logo-bar` |
| Part Heading / Overline / visible copy | Include `DELETE-ME` + issue key | Heading: `DELETE-ME I99X-339 Our clients` |
| Media uploaded for the test | Same prefix in display name | `DELETE-ME — I99X-339 — logo-1` |

Search in Content Studio for `DELETE-ME` or `delete-me-i99x-` to list leftovers.

**Do not** use generic names (`QA Parts Sandbox`, `test`, `Untitled`).

## Procedure (review)

1. Base: `https://review.i99x-group.k8s.seeds.no/`
2. CS: `https://review.i99x-group.k8s.seeds.no/admin/com.enonic.app.contentstudio/main` → project **English** → site **99x** (or whatever the review site root is named).
3. **New** → **Landing page** under the site (or a dedicated `_test` folder if one exists — still keep DELETE-ME in the name).
4. Set Display Name / Title / path per table above → **Save**.
5. Context panel → **Page** widget → controller **Default** → **Insert** the part under test.
6. Fill Inspect with **identifiable** copy and media (see per-part tips below) so screenshots clearly show *this* ticket’s component.
7. **Publish** (include image deps) → open live URL:
   `https://review.i99x-group.k8s.seeds.no/<path-name>`
8. After evidence: human deletes the landing page + any `DELETE-ME` media created for the run.

## Per-part identifiable config (minimum)

### Client Logo Bar (I99X-339)
- Heading: `DELETE-ME I99X-339 Our clients`
- Logos: ≥3 images named `DELETE-ME — I99X-339 — logo-N` (or reuse existing site logos only if heading alone uniquely IDs the shot — prefer dedicated uploads when practical)
- Auto-scroll (marquee) and `prefers-reduced-motion` cannot be shown by a still image — sample the CSS transform twice and read `getAnimations()`, and emulate reduced motion via CDP (see [_shared/How-to-instrument-live-pages-with-cdp.md](../_shared/How-to-instrument-live-pages-with-cdp.md)).

### Content Block (I99X-341)
- Overline: `DELETE-ME I99X-341`
- Heading: `DELETE-ME I99X-341 Content Block`
- Body: short unique sentence including the issue key
- With-image variant: image `DELETE-ME — I99X-341 — hero`; Position Left then Right as needed
- Link text: `DELETE-ME read more`
- Pick a **high-contrast photo** for the image: a white-on-cream logo makes image-position evidence unreadable.
- Do **not** point an internal link at the site root — `pageUrl({ id })` resolves the site root to an empty string, producing a dead `read more`. Use a published inner page.
- Heading size is derived (no editor control): larger with an image, smaller in the no-image variant — measure `font-size` and quote both numbers rather than claiming it visually.

### Expandable Link List (I99X-343)
- Overline: `DELETE-ME I99X-343 What we do`
- ≥2 rows; Link Text includes issue key (e.g. `DELETE-ME I99X-343 Row A`); at least one row with Description for hover-expand; optional images prefixed `DELETE-ME — I99X-343 — …`
- Inheritance target must be an **Article** (has `title` + `intro` + `image`). On this site Article also requires an **Offering** reference — create a disposable Offering if none fits. Publish the Article with the page or Content rows lose live `href`s.
- **Styled version is live since the prototype merge** — hover-expand, image panel and arrows all render on review; plan evidence for them instead of treating them as deferred.
- Live DOM: `.expandable-link-list__row` (one per row), `.expandable-link-list__panel` (present only when a description exists), `.expandable-link-list__image--active`; arrow glyph class `lucide-arrow-right` (internal) vs `lucide-arrow-up-right` (external `target=_blank`).
- Image panel is `hidden lg:block` (absent at mobile widths) and disappears entirely when **no** row has an image; hovering a row **without** an image keeps the previous image (deliberate — never blank), which is a documented deviation from "empty placeholder".
- Hover activation is gated by `matchMedia('(hover: hover) and (pointer: fine)')`, so it cannot be exercised with touch emulation.
- Row hover needs a React-friendly synthetic event — see [_shared/How-to-instrument-live-pages-with-cdp.md](../_shared/How-to-instrument-live-pages-with-cdp.md).

### Article layout (I99X-388)
- **Kind:** Layout `no.seeds.99x:article` (`cms/layouts/article/`, `addLayout`), no config form — every value comes from the Article item itself.
- Disposable Article: `DELETE-ME — I99X-388 — Article Layout` / `delete-me-i99x-388-article-layout`, created under `/99x/Insights/blog` (breadcrumb needs real ancestors: site → `Insights` → `Blog`).
- Fields to fill for full coverage: `title`, `intro`, `image` (hero), `author` (Employee that has **both** `name` and `title`, e.g. under `/99x/employees`), `offering` (mandatory, becomes the chip row), and `body` containing a paragraph, a `<figure><img src="image://<uuid>"/>` , a `[quote quote="…" attribution="…"/]` macro, an `<a href="content://<uuid>">` link and a bullet list — that single body proves inline RichText + macros + link resolution at once.
- Page: controller `no.seeds.99x:default` → `LayoutComponent` `no.seeds.99x:article` in `main`; drop existing parts (`no.seeds.99x:list-people`, `no.seeds.99x:newsletter-signup`) into the **layout's own** `main` region to prove the dropzone below the author signature.
- Stub DOM (backend stub View, unstyled): `article` > `nav[aria-label=Breadcrumb]`, `h1`, intro `p`, chip `ul`, hero `img`, RichText body, author `p`, then the region components.
- **Default-page wiring is not done on review:** `/99x/_templates/default` supports `no.seeds.99x:article` but its `main` region still holds the legacy part `no.seeds.99x:fullView`, so new Articles do **not** get this layout. Applying it requires a Content Studio template change (a manual step per CLAUDE.md), not code.

### List People (I99X-353)
- Landing: `DELETE-ME — I99X-353 — List People` / path `delete-me-i99x-353-list-people`
- Part Overline / Title: include `DELETE-ME I99X-353`
- Employees under `/99x/employees`: Person A (full: name, title, location TextLine, email, phone); Person B (name only — omit-empty); C–E (name + title) for five-card multi-select
- Content types on REST use app prefix: `no.seeds.99x:employee`, `no.seeds.99x:landing-page`, part descriptor `no.seeds.99x:list-people`
- Stub DOM: `.list-people__person`, `.list-people__location`, `a.list-people__email[href^="mailto:"]`, `a.list-people__phone[href^="tel:"]`, `ul.list-people__people` (no carousel chrome)

### Card Grid (I99X-363)
- Landing: `DELETE-ME — I99X-363 — Card Grid` / path `delete-me-i99x-363-card-grid`
- Separate disposable Landing as link target: `DELETE-ME — I99X-363 — link target` / `delete-me-i99x-363-link-target` (publish with the page)
- Part descriptor: `no.seeds.99x:card-grid`
- Config: Overline + Title + Cards ItemSet (`header`, `text`, `linkText`, `linkContent` Reference, `externalLink`) — text-only (no image/icon/colour)
- Minimum cards for evidence: A (internal link), B (no link fields), C (external only), D (both linkContent + externalLink — internal must win), E–F (count fillers, no links)
- Stub DOM: `section.card-grid`, `.card-grid__overline`, `.card-grid__title`, `ul.card-grid__cards` > `li.card-grid__card`, optional `a.card-grid__card-link`
- Live asserts: Card B has no `.card-grid__card-link`; Card D `href` is internal path and the competing external URL string is absent; ≥6 `.card-grid__card`
- Inspect tip: click `.card-grid` inside the draft iframe, then **Expand all** on Cards ItemSet to see Header/Text/Link fields

### Featured Cards (I99X-345)
- Source folder: `DELETE-ME — I99X-345 — cards source` / `delete-me-i99x-345-cards-source` (`base:folder`) under `/99x`
- Card children: prefer **Landing page** (`no.seeds.99x:landing-page`) with `title` + optional `image` — Reference requires industry/offering/location
- Paths: `delete-me-i99x-345-card-a|b|c`; junk sub-folder `delete-me-i99x-345-junk-folder` (must not become a card)
- Landing: `DELETE-ME — I99X-345 — Featured Cards` / `delete-me-i99x-345-featured-cards`; part `no.seeds.99x:featured-cards`
- Config: Overline/Title, `sourceFolder` (folder only), `maxItems`, `cardsOverride` ItemSet, View All FieldSet
- Stub DOM: `section.featured-cards`, `.featured-cards__overline`, `.featured-cards__title`, `a.featured-cards__card`, optional `.featured-cards__view-all`, empty auto-list labels (no `.featured-cards__card-label`)
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-345-featured-cards`
- REST create `parent` must be a **content path** (e.g. `/99x`), not the site UUID
- Session: XP 8 review uses `JSESSIONID` (not `SessionID`); recoverable from Firefox `sessionstore-backups/recovery.jsonlz4` when cookies.sqlite has no row


### Contact CTA (I99X-365)
- Landing: `DELETE-ME — I99X-365 — Contact CTA` / path `delete-me-i99x-365-contact-cta`
- Part descriptor: `no.seeds.99x:contact-cta`
- Config: `heading`, `contactPerson` (Reference → `employee`), `accordionLabel`, `emailReceiver` (required TextLine), `privacyLink` (Reference)
- Prefer an existing Employee with `picture` + `email` + `phoneNumber` (e.g. under `/99x/employees`); privacy → `/99x/compliance/privacy-policy` when present
- Email Receiver for tests: throwaway only (e.g. `qa-i99x-365@example.invalid`) — review/dev MTAs can attempt real delivery
- Stub DOM (when JAR includes the part): `section.contact-cta`, `__portrait`, `__heading`, `__talk-to`, `__pills`, `details.contact-cta__accordion` (collapsed by default), form fields `userName` / `userEmail` / `userPhone` / `userMessage` / `consent` / `newsletter`, hidden `contentId` + `componentPath`, action → `/_/service/no.seeds.99x/sendFormEmail`
- **Assert** configured `emailReceiver` string is **absent** from rendered HTML; receiver is resolved server-side only
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-365-contact-cta`
- **Preflight deploy check:** draft must **not** show `Part descriptor:no.seeds.99x:contact-cta not registered in ComponentRegistry!`; `POST /_/service/no.seeds.99x/sendFormEmail` must not return `sendFormEmail.js` ResourceNotFound. If either fails, review JAR is behind `origin/review` — redeploy before evidence. Client registry chunk should contain `addPart("no.seeds.99x:contact-cta"`.
- WARNING — submit is FE+BE E2E (form `fetch` → service → Sent button); do not treat HTML-only or curl-only as full AC5/AC7 proof

### Upcoming Events (I99X-359)
- Events folder: `DELETE-ME — I99X-359 — events` / `delete-me-i99x-359-events` (`base:folder` under `/99x`)
- Events (content type `no.seeds.99x:event`): A (future + image), B (future, no image), C (past — must not list), optional nested D under a subfolder (descendants scope)
- Required Event deps: reuse existing site `eventType` + `location` (both required on the CT); DateTime fields as `LocalDateTime`; timezone e.g. `Europe/Oslo`
- Link target Landing: `delete-me-i99x-359-link-target`
- Part landing: `DELETE-ME — I99X-359 — Upcoming Events` / `delete-me-i99x-359-upcoming-events`; descriptor `no.seeds.99x:upcoming-events`
- Config: `overline`, `title`, `eventsFolder` (folder Reference), optional `maxCount` (empty → default **2**), Link FieldSet `linkText` / `linkContent` / `externalLink`
- Stub DOM (when processor runs): `section.upcoming-events`, `__overline`, `__title`, `__view-all`, `ul.upcoming-events__cards` > `li.upcoming-events__card-item`, optional `__card-image`, `__card-category`, `__card-title`, `__card-location-date`
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-359-upcoming-events`
- **Deploy check before evidence:** curl the live page’s `react4xp.<hash>.js` and assert `upcoming-events__` is present; hydrate `regions.main.components[0]` must include a `data` object (not descriptor-only). A green `review` pipeline alone is not enough if the XP pod still serves an older JAR/bundle (seen 2026-07-31: pipeline #85693 built `upcoming-events.js` but live hash `42698669021e05d2` lacked the BEM prefix).

### Article List layout (I99X-385)

- **Kind:** Layout `no.seeds.99x:article-list` (`cms/layouts/article-list/`, `addLayout` — **not** a Part). Insert via Page widget **Layout** or CS REST `page/update` with `{ LayoutComponent: { descriptor, config, regions: [{ name: 'main', components: [] }] } }`.
- Landing: `DELETE-ME — I99X-385 — Article List` / path `delete-me-i99x-385-article-list`
- Query source = the **page the layout sits on** (no folder selector). Type options = **direct child folders** of that page; type match = **first path segment only** (`type=web` must not match folder `web-design`).
- Disposable tree under landing: folders `web` / `web-design` / `design`; ≥3 articles under `web`, 1 under each other folder; 1 `remoteArticle` under `web` with external `url`.
- Offerings (required on article + remoteArticle): disposable `no.seeds.99x:offering` with unique DELETE-ME titles; **`relatedContent` must reference already-published content** (e.g. an existing landing) — pointing at site root `/99x` made publish fail with `Failed to publish 3 items`.
- Config: `heading`, `intro`, `sortBy` (`publish.first` \| `modifiedTime` \| `displayName`), `numberOfItems` (evidence often **2** for pagination).
- Hardcoded query params (never i18n-derived): `type`, `service`, `page`. Service wire value = offering **display** (`data.title || displayName`), URL-encoded.
- Stub DOM: `section.article-list`, `__heading`, `__intro`, `__cards` > `__card-item`, `__card-type`, `__card-title`, `__card-intro`, `__card-read-more`, `__pagination` (`current / totalPages`). Filter chrome UI is frontend — prove filters via query-string E2E + hydrate `filters` / `selectedFilters` / extended `pagination`.
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-385-article-list`
- Datatoolbox layout query: `components.layout.descriptor LIKE '*:article-list'`
- Preflight: live `react4xp.<hash>.js` contains `article-list__` / `addLayout("no.seeds.99x:article-list"`; Inspect after selecting layout in Components tree → **Inspect** tab (not Insert).
- WARNING — `?type=` / `?service=` / `?page=` span FE↔BE; evidence must be live E2E on review, not CMS-only.

### Video Part (I99X-381)
- Landing: `DELETE-ME — I99X-381 — Video Part` / path `delete-me-i99x-381-video-part`
- Part descriptor: `no.seeds.99x:video` / Insert label **Video**
- Config fields: `youtubeVideoId` (TextLine, ID only), `videoUpload` (ContentSelector `allowContentType: media:video`), `thumbnail` (optional ImageSelector)
- Disposable media: upload `media:video` + poster `media:image` via CS REST  
  `POST /admin/rest-v2/cs/cms/<project>/content/content/createMedia` multipart (`name`, `parent=/99x`, `file=@…`)
- Config matrix (reconfigure Inspect / `page/update` between draft shots):
  - YouTube-only → iframe `https://www.youtube.com/embed/<id>?autoplay=0&mute=0` in `.videoWrapper--youtube.aspectRatio--16x9`
  - Hosted bare → `<video controls>` + `<source>` in `.videoWrapper--video`; **no** `.video-player__poster` / `.playButton`; no `autoplay`/`loop`/`muted`
  - Hosted + thumbnail → same `<video>` + `.video-player__poster` + `.playButton`
  - Precedence (both sources) → hosted path wins; **no** YouTube iframe; hydrate props omit `youtubeVideoId`
- Stub DOM: `.video-player`, `.videoWrapper--youtube|--video`, `.aspectRatio--16x9`, `.playButton`, `.video-player__poster`
- Hydrate / processor props: `variant: "part"`, flat `videoUrl` / `youtubeVideoId` / `thumbnail?: {src,alt}` (visible in live HTML page JSON)
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-381-video-part`
- Publish must include media UUIDs (`ids`: page + video + poster)
- Datatoolbox (XP 8 — **no** `/tool/` segment):  
  `/admin/systems.rcd.enonic.datatoolbox/data-toolbox#search?query=components.part.descriptor%20LIKE%20'*%3Avideo'`
- Preflight: client bundle contains `addPart("no.seeds.99x:video"`; draft must not show ComponentRegistry miss
- Session: recover `JSESSIONID` from Firefox `sessionstore-backups/recovery.jsonlz4` when cookies.sqlite has no review row; inject into Playwright if `cursor-ide-browser` unavailable
- WARNING — CMS Inspect + SSR stub DOM is FE+BE E2E for this part; do not treat schema-only or HTML-only in isolation as full proof

### Video Macro (I99X-379)
- **Host rule:** insert the macro in a **content-block** (preferred) or **text-block** HtmlArea Body — **not** Article `body` (no registered content-type View / processor yet).
- Landing: `DELETE-ME — I99X-379 — Video Macro` / path `delete-me-i99x-379-video-macro`
- Part on page: `no.seeds.99x:content-block` via CS REST `page/update` (`PartComponent`); Heading e.g. `DELETE-ME I99X-379 Video Macro host`
- Macro: bare name `video` (registered `addMacro("video"` — no `app.name:` prefix). Descriptor title **Video**, description *Inline 16:9 video player for RichText fields*
- Insert Macro UI: Content Block Inspect → Body CKEditor → toolbar **Insert macro** → pick **Video** → Configuration shows **Video (YouTube ID)**, **Video Upload**, **Thumbnail**
- Stored HtmlArea body (macro instruction): `[video youtubeVideoId="…" videoUpload="<uuid>" thumbnail="<uuid>"/]` (omit unused attrs)
- Disposable media: `createMedia` multipart under `/99x` (`media:video` + poster `media:image`); YouTube test ID only: `jNQXAC9IVRw`
- Config matrix (edit Body macro / `page/update` between draft shots):
  - YouTube-only → idle `.video-block.video-block--macro.aspectRatio--16x9` + `.video-block__play` (no iframe until play)
  - Hosted + thumbnail → `.video-block__poster` + `.video-block__play` (no native `<video>` until play)
  - Hosted, no thumbnail → direct `<video controls src=…>` (no poster/play overlay; no `loop`/`autoplay` on idle)
  - Both sources → **upload wins**: poster/hosted path only; **no** YouTube iframe; processor omits `youtubeVideoId`
- After play (live, hydrated): hosted → `<video controls autoplay>` **without** `loop`; no YouTube iframe when upload set
- Stub DOM selectors: `.video-block`, `.video-block--macro`, `.aspectRatio--16x9`, `.video-block__poster`, `.video-block__play`
- Live URL: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-379-video-macro`
- Preflight: review client bundle contains `addMacro("video"` / `video-block--macro`; draft must not show macro-not-registered
- Draft CS iframe often **SSR-only** (play click may not hydrate) — prefer **live** public URL for after-play asserts
- WARNING — CMS HtmlArea macro config + React4XP stub render is FE+BE E2E; do not treat schema-only as full proof

### Newsletter Signup (I99X-357)
- Landing EN: `DELETE-ME — I99X-357 — Newsletter Signup` / `delete-me-i99x-357-newsletter-signup`
- Optional privacy target: `delete-me-i99x-357-privacy-target` (or link HtmlArea to existing `/99x/compliance/privacy-policy`)
- Part descriptor: `no.seeds.99x:newsletter-signup`
- Config fields only: `title`, `description`, `fieldLabel`, `privacyText` (HtmlArea `exclude: "*"` / `include: "Link Unlink"` — no Privacy Link ContentSelector; no theme/background; no placeholder/Subscribe fields)
- Privacy HtmlArea internal link: `<a href="content://<uuid>">…</a>` → live resolves (e.g. `/compliance/privacy-policy`)
- Stub DOM: `section.newsletter-signup`, `__intro`, `__title`, `__description`, `__form` (`method="post"`), `__field-label`, `__input[type=email][required]`, `__submit`, `__privacy`
- Fixed chrome via i18n: EN `Enter your email` / `Subscribe`; NO `Skriv inn e-postadressen din` / `Meld deg på` (`phrases_no.properties`)
- Live EN: `https://review.i99x-group.k8s.seeds.no/delete-me-i99x-357-newsletter-signup`
- Live NO (norwegian project publish): `https://review.i99x-group.k8s.seeds.no/no/delete-me-i99x-357-newsletter-signup` — CS project key **`norwegian`** (site language `no`)
- Inert submit: fill email + click Subscribe — URL must **not** gain `?email=`
- AC7: clear all optional config → publish → placeholder/Submit still render
- Session: recover `JSESSIONID` from Firefox `sessionstore-backups/recovery.jsonlz4` (needs `lz4`); CS REST as `user:system:su`

## Pitfalls

- Localhost runs are **study only** — never attach local screenshots as formal Jira evidence for these tickets.
- Review `/admin` needs a logged-in session (user fills). Cold Playwright has no session — `POST /admin/_/idprovider/system` with JSON `{"action":"login","user":"…","password":"…"}` sets `JSESSIONID` (XP 8).
- Live path may differ if the review site root is not `99x` — confirm tree root after login; map `_path` → public URL by stripping `/content/<site>` (or site name segment) per vhost.
- **Insert Part by drag** often fails under browser automation — use the CS REST `page/update` fallback in [_shared/How-to-use-content-studio-xp8.md](../_shared/How-to-use-content-studio-xp8.md) (typed `PartComponent` wrapper + PropertyArray `config`), then reload draft/edit.
- Publish may need **Mark as ready** first (`workflow.state` was `IN_PROGRESS`); REST: `markAsReady` → `publish` with `ids` including image deps.
- CS `content/query` requires `contentTypeNames` (non-null). Create uses `parent` as **path** (e.g. `/99x`), not content UUID.
- CS delete body uses `contentPaths` (not `contentIds`) on this CS 6 build.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Review base | `https://review.i99x-group.k8s.seeds.no/` |
| CS | `https://review.i99x-group.k8s.seeds.no/admin/com.enonic.app.contentstudio/main` |
| Search leftover | `DELETE-ME` |
