# How to verify /video Qbrick archive on NTF review

**Scope:** `ntf`  
**Applies to:** review (`https://review.ntf.seeds.no/`)  
**Related:** [How-to-test-NTF-security-services-on-review.md](./How-to-test-NTF-security-services-on-review.md)

## Prerequisites

- Public access to review (no `/admin` auth)
- Cookiebot: marketing **denied** to see the featured-player placeholder; marketing **accepted** to see the live Qbrick player
- GitLab web login only if capturing source diffs

## Procedure

### 1. Open the video archive

Navigate to `{base}/video`.

Expect featured player (or placeholder) plus a grid of tiles and paging links under `nav.tabs`.

### 2. Cookie-consent placeholder (marketing denied)

1. Open Cookiebot (`Cookiebot.renew()` or the cookie widget).
2. Leave **Markedsføring** unchecked; click **Tillat utvalg**.
3. Reload `/video`.
4. Confirm `.qbrick-player-placeholder` is visible (`display` not `none`) with text **Godta informasjonskapsler for å se video**.

Selectors:

| Element | Selector / note |
|---------|-----------------|
| Placeholder | `.qbrick-player-placeholder` |
| Consent copy | `.qbrick-player-placeholder__text` |
| Marketing checkbox | `#CybotCookiebotDialogBodyLevelButtonMarketing` |
| Allow selection | `#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowallSelection` |

### 3. Next / previous paging

| Page | URL | Expect |
|------|-----|--------|
| First | `/video` | Link **Neste** → `/video?c=&offset={limit}` (review content uses limit ≈ 9 → `offset=9`) |
| Last | `/video?c=&offset=3600` (or any offset past the catalog) | **Forrige** present; **Neste** absent |

`endofline` is derived from the over-fetched grid (`limit+5`); no separate `testnext` Qbrick query.

### 4. Booster cache caveat (timing)

```bash
curl -sS -D - -o /dev/null "{base}/video" | rg -i 'Cache-Status|Age:'
```

`Cache-Status: Booster; hit` means edge TTFB is **not** XP cold-render time. Do not use public curl timing to prove controller ms targets.

### 5. Source checks (performance ACs)

GitLab commit / blob on `review`:

- `football/src/main/resources/site/layouts/videoside/videoside.js` — `testplayer.thumbnail = qlibresponse.thumbnail`; `endofline` from `testlibcall.length`
- `football/src/main/resources/lib/qbrick.js` — `settings.thumbnail` preferred in `getPlayer`; `connectionTimeout: 5000` / `readTimeout: 10000` on all four `httpClientLib.request` sites

## Pitfalls

- **Booster HTML cache** — cached responses hide backend timing; source + functional paging/placeholder are the honest evidence paths.
- **Placeholder `background-image` HTML quotes** — `style="background-image: url("https://…")"` breaks attribute parsing (CDN path can appear as bogus attributes). Consent overlay still shows; thumbnail paint may be blank. Pre-existing relative to NTF-1173 placeholder markup.
- **Cookiebot already consented** — if marketing is on, placeholder is `display: none` and the player initializes; renew and deny marketing, then reload.
- **Category sidebar `undefined`** — separate content/config issue on review; unrelated to Qbrick round-trip optimization.
- Last-page offset is catalog-size dependent; prefer a high offset (`3600`+) over walking every page.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.ntf.seeds.no/` |
| Video path | `/video` |
| First-page Next | `/video?c=&offset=9` |
| Last-page probe | `/video?c=&offset=3600` |
| Fix commit (NTF-1225) | `180756cd443a445d426e02f6b520cbde930221fc` |
