# How to test Minside tickets QR modal on NTF club host

**Scope:** `ntf`  
**Applies to:** Club staging hosts (e.g. `https://rbk.ntf.seeds.no/`)  
**Related:** [How-to-test-Enonic-admin-su-login-on-NTF-hosts](./How-to-test-Enonic-admin-su-login-on-NTF-hosts.md)

## Prerequisites

- Idrettens ID login (Minside) — **user fills** credentials in browser
- Account linked to Ticketco email with active and/or expired tickets (optional; see pitfalls)
- Fix deployed: `ticketsModal.js`, `ntfpwa/ntfpwa.js`, club CSS (`compiled/css/{club}.css`)

## Procedure

1. Open Minside tickets tab: `{base}/minside?ticket=true`
2. Confirm **BILLETTER** tab is active.
3. **Active ticket regression:** click an active `.tickets__row` (outside `#expiredTickets`).
   - Expected: fullscreen `.ticketModal` opens (`display: block`), wallet CTA visible.
4. Close modal (`.closeModal` or backdrop).
5. Click **Vis tidligere kjøpte billetter** (`.expiredTicketsButton`).
   - Expected: AJAX loads `#expiredTickets`; historic rows appear.
6. Confirm small QR on expired card: `.qrcode img` inside `#expiredTickets .ticket`.
7. Click expired `.tickets__row`.
   - Expected: no modal, no scroll lock (`body.style.overflowY` not `hidden`).
8. Hover expired card; check cursor on row, `.ticket`, `.ticket__link`.
   - Expected: `cursor: default` (not `pointer`).

### Console verification (after step 7)

```javascript
({
  modalDisplay: document.querySelector('.ticketModal')?.style.display,
  bodyOverflow: document.body.style.overflowY,
  expiredLinkCursor: getComputedStyle(document.querySelector('#expiredTickets .ticket__link')).cursor,
  expiredRowCursor: getComputedStyle(document.querySelector('#expiredTickets .tickets__row')).cursor
})
```

Expected: `modalDisplay` not `block`, `bodyOverflow` not `hidden`, cursors `default`.

### Deploy sanity (no browser)

```bash
# From page HTML, resolve asset URLs under /_/asset/no.seeds.app.football:...
curl -sS '{base}/minside?ticket=true' | rg 'ticketsModal|ntfpwa'
curl -sS '{asset}/js/ticketsModal.js' | rg 'closest\("#expiredTickets"\)'
curl -sS '{asset}/js/ntfpwa/ntfpwa.js' | rg 'ticketModalHandler'  # should NOT appear in expired AJAX .done()
```

### Mobile viewport

Resize to ~375px width; repeat step 3. Modal should still open for active tickets.

## Pitfalls

- **Staging test settings required:** Real Ticketco test tickets (active + expired) depend on staging test configuration. Without it, the page shows "Ingen aktive billetter" / "Ingen tidligere billetter" — do not use synthetic DOM injection for Jira evidence unless test data is unavailable and that limitation is documented.
- **No Ticketco tickets:** If test settings are missing, restore staging test config before capturing evidence.
- **`sessionStorage.allowExpiredTickets`:** Second click on expired button only toggles visibility; clear with `sessionStorage.removeItem('allowExpiredTickets')` before retesting AJAX load.
- **Compiled CSS:** `compiled/` is gitignored; staging must run `gulp build` so `_tickets.scss` changes reach `compiled/css/{club}.css`.

## Sample data

| Item | Value |
|------|-------|
| Base URL | `https://rbk.ntf.seeds.no` |
| Test path | `/minside?ticket=true` |
| Expired button | `.expiredTicketsButton` — label **Vis tidligere kjøpte billetter** |
| Expired container | `#expiredTickets` |
| Modal | `.ticketModal` |
