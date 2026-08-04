# How to verify football site-lookup cache in source

**Scope:** `ntf`  
**Applies to:** GitLab `seeds/football` (any branch that contains the fix)  
**Related:** [How-to-verify-terminliste-ICS-cache-control.md](./How-to-verify-terminliste-ICS-cache-control.md)

## Prerequisites

- GitLab web session (or local git checkout)
- No public HTTP signal — site-lookup cache cannot be proven via curl headers

## Procedure

1. Open the fix commit (or blob on `staging`/`review`):

   - Commit: `https://git.seeds.no/seeds/football/-/commit/<sha>`
   - Files: `football/src/main/resources/lib/config/global.js` and `lib/util.js`

2. Pass when both modules show:
   - `var siteCache = cacheLib.newCache({ size: 10, expire: 60 * 10 })`
   - Cache key includes repo + branch: `"football-site_" + context.repository + "_" + context.branch`
   - Loader returns a **non-null sentinel** `{ id: sitesResult.hits[0] ? …._id : null }` (Guava throws `InvalidCacheLoadException` on null/undefined)
   - After cache get, re-resolve with `contentLib.get({ key: siteId })` (caches ID only, not the full site object)

3. Note: the two modules each create their **own** `siteCache` instance (not a shared singleton across modules).

## Pitfalls

- Do not use edge TTFB or Booster HTML hits as proof of site-lookup cache — unrelated layers.
- Live Trace / XP profiler is the only runtime latency confirmation (separate from source AC).
- Pre-harden key `"football-site"` alone let draft cron jobs poison master consumers for up to 10 min.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Harden commit (NTF-1226) | `6da0721daa790d3e66b82ee55d910ed255dbbb33` |
| Cache key pattern | `football-site_<repository>_<branch>` |
| TTL | 10 minutes (`60 * 10`) |
