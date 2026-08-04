# How to verify PWA precache manifest (NTF review / club staging)

**Scope:** `ntf`  
**Applies to:** review (`https://review.ntf.seeds.no/`) and club staging (e.g. `https://bra.ntf.seeds.no/`)  
**Related:** [How-to-test-NTF-security-services-on-review.md](./How-to-test-NTF-security-services-on-review.md)

## Prerequisites

- Public HTTP access to the target host (no admin auth for the read endpoint)
- GitLab web login only if capturing source evidence for the writer **task**

## Procedure

### 1. Fetch the live manifest

```bash
curl -sS "<base>/_/service/no.seeds.app.football/fetch_precache_routes"
```

Expect HTTP 200 JSON shaped as `{ routes: [{url, revision}, …], images: [{url, revision}, …] }`.

### 2. Assert no mangled absolute URLs

Pass when zero `routes`/`images` `.url` values match `^/?https?:` or contain `/https:/`.

```bash
# Example filter (jq): count mangled image/route URLs
curl -sS "<base>/_/service/no.seeds.app.football/fetch_precache_routes" \
  | jq '[.routes[].url, .images[].url] | map(select(test("^/?https?:|/https:/"))) | length'
# Expect: 0
```

Also confirm at least one same-origin image remains (`/_/image/` or `/_/asset/`).

### 3. Optional — homepage absolute `<img>` audit (club hosts)

```bash
curl -sS "<base>/" | grep -oE '<img[^>]+src="[^"]+"' | grep -E 'src="(https?:)?//' | grep -v "<base-host>"
```

On BRA staging (2026-07-23) partner logos were same-origin `/_/image/…` only — zero absolute `eliteserien.no` `<img src>`. Production-style external absolute logos may still exist only on `www.brann.no`.

### 4. Source guard (AC for external-URL skip)

Do **not** confuse these three names:

| Artifact | Path / URL | Role |
|----------|------------|------|
| Read service | `/_/service/no.seeds.app.football/fetch_precache_routes` | Public manifest for SW |
| Writer **task** | `football/src/main/resources/tasks/precache-routes/precache-routes.js` | Scrapes pages, writes repo |
| Other service | `services/precache-routes/…` | Not the skip-guard evidence target |

Skip guard (task file): absolute `rawUrl` where `rawUrl.indexOf(baseUrl) !== 0` → early `return` before `baseUrl` concat / OPTIONS.

GitLab examples:

- Commit: `https://git.seeds.no/seeds/football/-/commit/<sha>`
- Review blob: `…/-/blob/review/football/src/main/resources/tasks/precache-routes/precache-routes.js`
- Staging blob (BRA deploy): `…/-/blob/staging/football/src/main/resources/tasks/precache-routes/precache-routes.js`

## Pitfalls

- A clean manifest proves AC “well-formed” but **alone** does not prove the task stopped mangling external URLs when the host has no external absolute `<img>` — pair with the task source guard.
- Synthetic `GET …/https:/www.eliteserien.no/...` always yields HTML 404 (~tens of KB); that is the error-page cost pattern, **not** a pass signal for the fix.
- Image `revision` values update when the precache job runs; re-fetch before capture if you need “post-deploy” freshness.
- Club staging content can mix brands/data (e.g. BRA host with RBK partner copy) — still valid for same-origin vs mangled-path checks.
- Full production AC4 (`www.brann.no` external eliteserien logos → no mangled 404s) needs production after deploy when those absolute logos are present.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Review base | `https://review.ntf.seeds.no/` |
| BRA staging base | `https://bra.ntf.seeds.no/` |
| Manifest endpoint | `/_/service/no.seeds.app.football/fetch_precache_routes` |
| Task file | `football/src/main/resources/tasks/precache-routes/precache-routes.js` |
| Fix commit (NTF-1224) | `a9032de91d51086f7fde2b85d0785e0de6502471` |
