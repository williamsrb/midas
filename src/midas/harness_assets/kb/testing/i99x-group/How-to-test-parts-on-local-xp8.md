# How to test i99x-group Parts on local XP 8 (study only)

**Scope:** `i99x-group`  
**Applies to:** local Docker XP (`i99x-xp-app` on `:8080`) — **instrumentation / study only**  
**Not for:** formal Jira evidence. Real evidence runs on review — see [How-to-create-disposable-part-test-content-on-review.md](./How-to-create-disposable-part-test-content-on-review.md).  
**Related:** [_shared/How-to-use-content-studio-xp8.md](../_shared/How-to-use-content-studio-xp8.md), [How-to-verify-review-environment.md](./How-to-verify-review-environment.md)

## Prerequisites

- Containers up (`make up` run by the user); app JAR deployed (`99x-1.0.0.jar` in deploy).
- Admin logged in at `http://localhost:8080/admin`.
- Parts present in JAR: `client-logo-bar`, `content-block`, `expandable-link-list`.

## Vhosts → live URLs

From `docker/dev/xp-home/config/com.enonic.xp.web.vhost.cfg`:

| Host | Public path | Site engine target |
|------|-------------|--------------------|
| localhost | `/` | `/site/english/master/99x` |
| localhost | `/no` | `/site/norwegian/master/99x` |
| localhost | `/admin` | `/admin` |

Content `_path` `/99x/<slug>` → live English URL `http://localhost:8080/<slug>`.

## Procedure

Same click path as review (project English → site 99x → New Landing page → Page widget → Insert part → Publish). Use any throwaway names locally; do not treat local content as evidence artifacts.

### Attach Default page + insert part

1. Open the landing page editor (direct edit URL preferred).
2. Context panel → widget **Page**.
3. Assign page controller **Default** (`no.seeds.99x:default`, region `main`).
4. **Insert** → Part → pick Client Logo Bar / Content Block / Expandable Link List.
5. Fill Inspect → **Save** → **Publish**.
6. Live check under `http://localhost:8080/<slug>`.

## Pitfalls

- Live URL **500** until the page has a working controller and content is on **master**.
- Folder `/99x/test` may reference old unregistered parts — prefer a fresh Landing page.
- **Never** upload local screenshots to Jira as delivery evidence for I99X-339/341/343.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base | `http://localhost:8080` |
| Site | `/99x` (english project) |
| App | `no.seeds.99x` |
| Formal evidence host | `https://review.i99x-group.k8s.seeds.no/` |
