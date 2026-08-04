# How to verify RSS and manifest cache headers (NTF club host)

**Scope:** `ntf`  
**Applies to:** club staging / review (`https://{host}.ntf.seeds.no/`)  
**Related:** [How-to-verify-terminliste-ICS-cache-control.md](./How-to-verify-terminliste-ICS-cache-control.md), [How-to-verify-PWA-precache-manifest-on-review.md](./How-to-verify-PWA-precache-manifest-on-review.md)

## Prerequisites

- Public HTTP access
- Content `rss-nyheter` (`com.enonic.app.rss:rss-page`) must exist on the site — otherwise `/rss-nyheter` is HTML 404. Create via `GET {base}/_/service/no.seeds.app.football/form-rss` when missing (service account path; may 404 if routing hides the service URL).

## Procedure

### Manifest

```bash
curl -sS -D - -o /tmp/manifest.json --max-time 20 "{base}/manifest.json"
```

Pass: HTTP 200, `application/json`, club `name`/`short_name` present, `Cache-Control: public, max-age=86400` (24h from `mappings/manifest.js`).

### RSS feed body

```bash
curl -sS -D - -o /tmp/rss.xml --max-time 30 "{base}/rss-nyheter"
```

Pass (functional): HTTP 200, `application/xml` (or `text/xml`), body contains `<rss` and a `<channel><title>`.

### RSS Cache-Control (AC-critical)

Expect: `Cache-Control: public, max-age=180` from filter `mappings/rss-cache.js` matched in `site.xml` on `type:'com.enonic.app.rss:rss-page'` at **`order="8"`** (must beat catch-all `partner-redirect-login.js` at `order="10"` — XP picks one mapping; ties break by declaration order).

Also expect: `Content-Type: application/xml; charset=utf-8` (source sets `UTF-8`; XP lowercases on the wire — match case-insensitively). Body starts at `<rss …>` (no `<?xml` declaration). Non-ASCII titles must be valid UTF-8 (`å` / `é` / `ø`), not Latin-1 mojibake.

**Known failure mode (NTF-1226 on BRA before harden):** ICS and manifest already showed Cache-Control, but `/rss-nyheter` had no Cache-Control because both filters were `order="10"` and the catch-all won. Fixed by `order="8"` in commit `6da0721da`.

Sanity check that other NTF-1226 headers work on the same host before blaming deploy lag:

```bash
curl -sS -I "{base}/terminliste/subscribe" | rg -i 'cache-control'
curl -sS -I "{base}/manifest.json" | rg -i 'cache-control'
curl -sS -I "{base}/rss-nyheter" | rg -i 'cache-control|HTTP/|content-type'
```

### Per-host RSS isolation

`/rss-nyheter` is the same path on every club. Cache key is `path_branch_host` and live/master-only. Probe two clubs:

```bash
curl -sS "{base_a}/rss-nyheter" | rg -o '<channel>[[:space:]]*<title>[^<]+'
curl -sS "{base_b}/rss-nyheter" | rg -o '<channel>[[:space:]]*<title>[^<]+'
```

Pass when both have `max-age=180` and channel titles differ (e.g. `Nyheter / Brann` vs `Nyheter / Rosenborg`).

## Pitfalls

- Host without `rss-nyheter` content → HTML 404; fix content first, then re-check headers.
- `review.ntf.seeds.no` and some clubs already have the content; BRA may need `form-rss` once.
- Do not confuse `/_/service/…/fetch_precache_routes` (PWA route manifest) with `/manifest.json` (Web App Manifest).
- Do not assert `<?xml` on the feed body — the app.rss renderer does not emit a declaration.
- Draft/preview must not populate the live RSS cache (`req.mode !== 'live'` or non-`master` → bypass).

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://bra.ntf.seeds.no` |
| Second host (isolation) | `https://rbk.ntf.seeds.no` |
| RSS path | `/rss-nyheter` |
| Manifest path | `/manifest.json` |
| Expected RSS Cache-Control | `public, max-age=180` |
| Expected RSS Content-Type | `application/xml; charset=utf-8` |
| Expected manifest Cache-Control | `public, max-age=86400` |
| Harden commit (NTF-1226) | `6da0721daa790d3e66b82ee55d910ed255dbbb33` |
