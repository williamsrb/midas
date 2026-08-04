# How to run Live Trace HTTP sampling on NTF club hosts

**Scope:** `ntf`  
**Applies to:** club staging with Live Trace installed (`https://{host}.ntf.seeds.no/admin/tool/com.enonic.app.livetrace/livetrace`)  
**Related:** [How-to-verify-rss-and-manifest-cache-headers-on-club-host.md](./How-to-verify-rss-and-manifest-cache-headers-on-club-host.md)

## Prerequisites

- XP admin session (IdP / shared admin — not `su`/`password` on hardened hosts)
- Live Trace license present (header shows “Issued to …”)
- WebSocket to the XP node must work for sampling (nginx must proxy WS). If the UI shows “WebSocket connection failed”, sampling may still work once connected, or fail until ops fixes the front proxy.

## Modes

| Tab | Use for |
|-----|---------|
| **Dashboard** | Node / cluster / JVM memory / threads overview — not per-URL span proof |
| **HTTP** | Per-request timings + expand spans (filters, controllerScript, content.find) — **AC5** |
| **Tasks** | Background jobs |

## Procedure (HTTP sampling)

1. Open `{base}/admin/tool/com.enonic.app.livetrace/livetrace` → **HTTP** tab.
2. Click **Start Sampling Data**.
3. Generate traffic (curl or browser) to the URLs under test, e.g.:
   ```bash
   for i in 1 2 3 4 5; do
     curl -sS -o /dev/null "{base}/rss-nyheter"
     curl -sS -o /dev/null "{base}/terminliste/subscribe"
     curl -sS -o /dev/null "{base}/manifest.json"
   done
   ```
4. Click **Stop Sampling Data**.
5. Use **Filter URL** (Enter) to isolate a path (`rss-nyheter`, `matches-calendar`, `manifest.json`).
6. Expand a row via the ▶ / `.lt-more-icon` control. Nested spans show `filter` / `filterScript` / `controllerScript` / `content …` with ms.
7. Compare **first** sample (often cold/miss) vs **later** samples (warm/hit). Do not use edge `curl` TTFB as XP render time.

## What “good” looks like (NTF-1226-style caches)

| Endpoint | Signal |
|----------|--------|
| `/rss-nyheter` | Cold: `filterScript /mappings/rss-cache.js` tens–hundreds of ms. Warm: total ~10–20 ms, `filter` ≪ 1–2 ms |
| `matches-calendar` | Cold: `controllerScript …/matches-calendar.js` expensive. Warm: controller ~1 ms, total single-digit–low tens ms |
| `/manifest.json` | Total often under prior 41–51 ms baseline; mapping still runs `renderComponent` |

## Pitfalls

- Dashboard charts go flat after Stop — expected; keep using the HTTP sample table.
- a11y tree may still list a stale “WebSocket connection failed” / “No license” modal text even when the UI is licensed and sampling works — trust the visible toolbar (“Sampling — N requests” / “N requests sampled”).
- Public HTML pages use `portalLib.getSite()`; the football `siteConfig.applicationKey` content.find may **not** appear in homepage traces. Prove site-lookup cache via jobs/services that call `contentGetSite`, or via absence of that query on paths that used to always hit it.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://bra.ntf.seeds.no` |
| Live Trace | `/admin/tool/com.enonic.app.livetrace/livetrace` |
| HTTP start control | button **Start Sampling Data** |
| Expander class | `.lt-more-icon` |
