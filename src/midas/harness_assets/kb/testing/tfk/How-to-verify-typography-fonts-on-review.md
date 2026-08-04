# How to verify typography fonts on TFK review

**Scope:** `tfk`  
**Applies to:** review (`review.tfk.k8s.seeds.no`)  
**Related:** TFK-61 / NTF-1213 typography project migration

## Prerequisites

- Public review sites — no auth
- Prefer league + club paths from the same host

## Procedure

1. Open a review site page, e.g. league `https://review.tfk.k8s.seeds.no/toppserien` or club `https://review.tfk.k8s.seeds.no/lsk`.
2. In DevTools / CDP `Runtime.evaluate`, read the typography stylesheet link:
   ```js
   document.querySelector('link[href*="cloud.typography.com"]')?.href
   ```
   Expect the **new** project id in the path (e.g. `6804032`), not the retired id (`7201172`).
3. Inspect computed styles on headings / nav / table headers:
   ```js
   getComputedStyle(document.querySelector('h2')).fontFamily
   getComputedStyle(document.querySelector('nav a, header a')).fontFamily
   ```
   League secondary/nav commonly uses Gotham XNarrow; club header/nav often DIN condensed; table headers may use Gotham XNarrow.
4. Confirm families in `document.fonts`:
   ```js
   [...new Set([...document.fonts].map(f => f.family))].sort()
   ```
   Expect `Gotham XNarrow A` (and DIN / Mulish as used by CSS). After migration away from the old typography project, Tungsten / Gotham regular usually disappear from this list.
5. Capture a viewport screenshot of league home + club home (and optionally `/lsk/tabell`, `/lsk/terminliste`) for before/after compare.
6. For source proof: open GitLab blob/commit for HTML head templates and `_fonts.scss` / `_match.scss` — remote `@import` of cloud.typography must be **absent**; fonts stay remote-only via HTML `<link>`.

## Pitfalls

- **Never** prove success by opening `https://cloud.typography.com/.../fonts.css` in a cold tab — domain whitelist returns FAQ/403 outside allowlisted hosts. Always check from the site page.
- `fetch(fonts.css)` from page JS may fail CORS even when the `<link>` loaded correctly — use `link.href` + `document.fonts` / Network for the stylesheet request instead.
- Before vs after: keep LSK paths aligned (`/lsk`, `/lsk/tabell`, `/lsk/terminliste`) for visual comparison.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.tfk.k8s.seeds.no/` |
| League path | `/toppserien` |
| Club path | `/lsk` |
| Typography project (new) | `6804032` |
| Typography project (old, retired) | `7201172` |
