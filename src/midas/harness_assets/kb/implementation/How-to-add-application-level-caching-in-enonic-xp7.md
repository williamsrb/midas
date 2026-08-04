# How to add application-level caching in Enonic XP 7 (site-lookup, third-party page renders, mappings)

**Scope:** `_shared`
**Applies to:** Enonic XP 7 apps using `/lib/cache` (`newCache`/`get`/`remove`), site.xml mappings/filters, mapping controllers, and `/lib/http-client` proxy handlers.
**Related:** NTF-1226 (site-lookup + non-HTML content caching, football repo)

## Prerequisites

- Identify the expensive call: a repeated `contentLib.query`/DB hit, or a render owned by code you don't want to fork (e.g. a third-party app's page controller).
- Confirm whether the endpoint is a `service` (custom controller, full control) or a `content` page rendered via a page-template/controller declared **on the content itself** (no mapping in `site.xml` will show up for it — check the content's `page.controller`, not `site.xml`, before assuming it's unmapped).

## Procedure

### 1. Cache a repeated content-lookup (e.g. a "the site" or "the config" query)

```js
var cacheLib = require('/lib/cache');
var cache = cacheLib.newCache({ size: 10, expire: 60 * 10 }); // dedicated, short TTL

var contentGetSite = function () {
    return cache.get("football-site", function () {
        return contentLib.query({ query: "...", contentTypes: [...] }).hits[0];
    });
};
```

- Use a **dedicated** cache instance with its own TTL, not an existing long-TTL general-purpose cache in the same module — different data has different staleness tolerance.
- A static cache key is safe **only** when the query result is single-tenant-per-instance **and** the code never runs under more than one branch/context — see "branch-aware keys" below before assuming this.
- Don't mutate the cached object in place if any caller does `obj.field = x` on the returned reference — cache misses become poisoned.
- **Cache only the ID, not the content, when the content is cheap to re-fetch by key.** `content.find` (query) is expensive (~30ms); `contentLib.get({key: id})` is cheap (~2ms). Caching `{ id: hits[0]._id }` and re-resolving by ID on every call keeps almost the whole win while eliminating an entire staleness class: the by-ID lookup always reads the current branch's live content, so there's no TTL window where a cached full-object copy serves stale config after a publish.
- **Never let a cache loader return `null`/`undefined` into `lib-cache`** — it delegates to Guava, which throws `InvalidCacheLoadException` on a null load. If the underlying query can legitimately find nothing, wrap the result: `cache.get(key, () => ({ id: hits[0] ? hits[0]._id : null })).id`. The wrapper is never null (Guava is satisfied); unwrapping `.id` still yields `undefined`/`null` to existing falsy-checking callers. Do **not** reach for a sentinel *content* object instead — a truthy sentinel will pass any caller's `if (site)` guard and then blow up on the next line that dereferences `site.data`.
- **Cache keys must be branch/context-aware whenever the same code path can run under more than one branch or mode.** A key like `"my-thing"` shared across draft and master lets a Content Studio preview, a cron job running in `context: { branch: "draft" }`, or an editor's edit-mode request populate the entry that live master traffic reads from, for the full TTL. Two independent, sufficient guards (use one or both):
  - Key on `contextLib.get().branch` (+ `.repository` if the app touches more than one repo): `cache.get(key + "_" + context.repository + "_" + context.branch, loader)`.
  - Or key on the request directly when in a filter/mapping/service with `req`: `req.mode` + `req.branch` + `req.host`, matching the existing pattern in `site/parts/latest-news/latest-news.js` (`"CachedNews_" + req.branch + "_" + req.host + "_" + req.mode + ...`).
  - Cheapest of all when the cache is meant for public traffic only: bypass the cache entirely (`return next(req)` / call the generator directly) unless `req.mode === 'live'` — previews and drafts always take the slow path, which is fine since they're not the traffic being optimized for.
  - A cron job's `context: {...}` option (via `/lib/cron`) really does change what `contextLib.get()` returns inside the callback — don't assume "it's just a background job, it won't touch the branch-keyed cache," verify the context block.

### 2. If the same query is duplicated in a second module (e.g. a private copy in a util lib)

Prefer delegating the duplicate to the now-cached primary implementation — **but check the require graph first**:

```
grep -n "require.*util" module-with-primary-impl.js       # does A require B?
grep -n "require.*module-with-primary-impl" util.js        # does B require A?
grep -rn "require('/lib/util')" **/*.js                    # does anything B depends on require B back?
```

If a delegate-to-A require from B would close a cycle through a third module (e.g. `A → shared/common.js → require('/lib/util') === B`), **don't add the require** — even though CommonJS-style engines usually tolerate lazy (function-scoped) circular requires by mutating the shared `exports` object in place, it's an unforced risk on XP's module loader. Instead give the duplicate its **own** small dedicated cache with the same key/TTL. Two small caches beat one fragile new require edge.

### 3. Cache a service response and its HTTP cache headers (e.g. ICS/calendar, generated feeds)

- If the handler already returns anti-cache headers (`Cache-Control: no-cache...`, `Pragma: no-cache`, `Expires: 0`), you must **replace all three**, not just add `max-age` — `no-cache`/`Pragma`/`Expires: 0` otherwise wins over `max-age` in most clients.
- Split the handler into `process(req)` (cache lookup + response envelope) and a pure `generateX(req)` (the expensive part) so `cache.get(key, () => generateX(req))` wraps only the costly work, and errors thrown inside `generateX` still propagate through `cache.get` to the existing try/catch.

### 4. If a 404-handler or `site/error/error.js`-style proxy fronts the real service via `httpClientLib.request(...)`

Proxies that do `return { body, contentType, status }` silently **drop response headers**, including any `Cache-Control` the real service now sets after step 3. Extract just what you need (don't blindly forward the full header map — that leaks hop-by-hop headers like `Content-Length`/`Transfer-Encoding` that don't make sense on the re-serialized response):

```js
function getCacheControlHeader(request) {
    var headers = request.headers || {};
    var key = Object.keys(headers).filter(function (k) { return k.toLowerCase() === 'cache-control'; })[0];
    return key ? { 'Cache-Control': headers[key] } : undefined;
}
```

### 5. Cache a page render owned by a third-party app, without forking it

If the endpoint is a **content page** (not a service) whose controller belongs to another installed app (e.g. `com.enonic.app.rss:rss`), you cannot easily re-invoke that controller from a `<mapping controller="...">` (controller mappings fully replace resolution — there's no "call the original" hook). Use a **filter mapping** instead, matched by content type, which does get `next(req)`:

```xml
<mapping filter="/mappings/my-cache.js" order="10">
  <match>type:'some.app:content-type'</match>
</mapping>
```

```js
exports.filter = function (req, next) {
    if (req.method !== 'GET') return next(req);
    return cache.get(req.path, function () {
        var response = next(req);               // triggers the real (expensive) render
        response.headers = response.headers || {};
        response.headers['Cache-Control'] = 'public, max-age=' + TTL;
        return response;
    });
};
```

On a cache hit, `next()` is never called, so the expensive render is skipped entirely — this is the key advantage over a `response-processor` (processors run *after* rendering and can't prevent it).

### 6. Two `site.xml` filter mappings at the same `order` — only one runs

XP dispatches **exactly one** filter mapping per request: `ControllerMappingsResolver` picks the lowest `order`, and ties break by **declaration order** in `site.xml` (first-declared wins). If you add a new filter at the same `order` as an existing catch-all (e.g. `<match>type:'.+'</match>`), and the catch-all is declared first, your filter **silently never runs** — no error, just a request that skips the mapping entirely with no diagnostic.

- Check every other `<mapping>` at the `order` you're about to use; either pick a free order value or one lower than any catch-all it needs to beat.
- Before assuming "my filter isn't running" is a code bug, check `order` ties first — it's indistinguishable from the filter having a logic error unless you read `site.xml` end to end.
- Confirm a new `order` doesn't unintentionally starve an *existing* filter that used to win the tie — read what that filter does for the content type in question before reordering.

### 7. Fixing "no charset" encoding errors on a render you can't fork

A third-party app's page render can emit non-ASCII bytes (e.g. Latin-1 "ø" = `0xF8`) with a `Content-Type` that has no `charset=`. Parsers then default to UTF-8 and reject the body ("encoding error"), even though the JS string itself is fine. If you can't fix the byte encoding at the source (upstream app, no fork), forcing an explicit charset on the response you build in your filter/wrapper (`contentType: 'application/xml; charset=UTF-8'`) makes the response serializer write UTF-8 bytes instead of falling back to an ambiguous platform default — this alone can resolve the mismatch without touching the third-party app. Verify in the actual deployed environment (Content Studio preview / a strict XML parser on the live response) before shipping — this can't be confirmed from source reading alone.

## Pitfalls

- Grepping `site.xml` for a mapping and finding nothing does **not** mean the URL is unhandled — content-path-matching URLs render via the content's own `page.controller`, bypassing `site.xml` mappings/services entirely.
- `response-processor` (site.xml `<processors>`) cannot skip a render — only a `filter` mapping (with `next(req)`) can.
- `local.club_id`-style single-tenant-per-instance apps make a static cache key safe for "the site"/"the club" lookups; don't assume this holds for multi-tenant setups without checking.
- In-process `newCache` clears on app redeploy — long TTLs (hours/days) are safe for near-static assets like a PWA manifest even across content/branding changes, since a redeploy resets the cache anyway.

## Sample data

Real example (football/NTF-1226): `lib/config/global.js` `contentGetSite` (cache key `"football-site"`), `services/matches-calendar/matches-calendar.js` (ICS cache keyed by request path), `mappings/rss-cache.js` (new filter mapping for `com.enonic.app.rss:rss-page`), `mappings/manifest.js` (cache keyed by club id).
