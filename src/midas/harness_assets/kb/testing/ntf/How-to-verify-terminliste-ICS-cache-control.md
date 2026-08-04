# How to verify terminliste ICS Cache-Control (NTF club staging)

**Scope:** `ntf`  
**Applies to:** club staging hosts (`https://{club}.ntf.seeds.no/`)  
**Related:** [How-to-verify-rss-and-manifest-cache-headers-on-club-host.md](./How-to-verify-rss-and-manifest-cache-headers-on-club-host.md)

## Prerequisites

- Public HTTP access (no admin auth)
- Fix deployed on the host’s branch (BRA → `staging`)

## Procedure

1. Fetch calendar subscribe:

```bash
curl -sS -D - -o /tmp/terminliste.ics --max-time 30 \
  "{base}/terminliste/subscribe"
```

2. Pass when all of:
   - HTTP 200
   - `Content-Type: text/calendar` (charset optional)
   - `Cache-Control: public, max-age=600` (ICS TTL = 10 min in `matches-calendar.js`)
   - Body starts with `BEGIN:VCALENDAR`

3. Optional second hit — same headers; body still valid ICS (app cache hit is opaque over HTTP).

### Unknown path must 404 (do not cache empty calendars)

```bash
curl -sS -D - -o /tmp/terminliste-missing.txt --max-time 15 \
  "{base}/this-path-does-not-exist-ntf1226/terminliste/subscribe"
```

Pass: HTTP **404**, `Cache-Control: no-store`, body `Not found` (not 200 empty ICS with `public, max-age=600`).

## Pitfalls

- Path is served via **404 error handler** → internal `matches-calendar` service; `error.js` must forward `Cache-Control` (`getCacheControlHeader`). Missing header on an otherwise-200 ICS body usually means the proxy dropped headers.
- Booster does **not** cache `text/calendar`; edge TTFB is not XP cold-render proof.
- Nested team paths (e.g. `…/sk-brann-kvinner/terminliste/subscribe`) use the same service with a path+branch+host cache key — root `/terminliste/subscribe` is enough for the base AC.
- Pre-harden bug: unknown paths returned 200 + empty calendar + `public, max-age=600` and poisoned the ICS cache for 10 min.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://bra.ntf.seeds.no` |
| Path | `/terminliste/subscribe` |
| Unknown path | `/this-path-does-not-exist-ntf1226/terminliste/subscribe` |
| Expected Cache-Control (valid) | `public, max-age=600` |
| Expected Cache-Control (unknown) | `no-store` |
| Harden commit (NTF-1226) | `6da0721daa790d3e66b82ee55d910ed255dbbb33` |
