# How to test contact-form submit services (gk)

**Scope:** `gk`  
**Applies to:** review / staging hosts derived from base URL  
**Related:** [How to search via Data Toolbox](../_shared/How-to-search-via-datatoolbox.md)

> **Note (GK-535 analyst decision):** Do **not** require `role:gk.contact-forms` for spam tests. Connect uses `role:system.admin`. The older ACL How-to is historical only.

## Prerequisites

- Public site base URL (no login for service curls)
- App key: `no.seeds.gk`
- Prefer `@example.invalid` emails; successful POSTs to submit/new-layout/multiple-recipients may send to real `mail_receivers`
- For seeding: logged-in XP admin + Data Toolbox `node-create` / `property-create`

## Procedure

1. Confirm public wiring:
   - `/kontakt-oss` → `data-service` includes `contact-form-with-multiple-recipients` and `contact-form-submit`
   - `/kampanjer/veiviser` → references `energy-calculator-contact`
2. Confirm repos exist (Data Toolbox Node Tree): `contact-forms-repo`, `contact-forms-repo-with-multiple-recipients`, `contact-forms-energy-calculator` (ensured by `addRepos()` in `main.js`).
3. Service base: `<base>/_/service/no.seeds.gk/<service>` (page-scoped `/kontakt-oss/_/service/...` also works).
4. Body shapes:
   - `contact-form-submit` / `contact-form-new-layout`: JSON array of `{name,value}` (new-layout uses **positional** `formData[1].value` as email)
   - `contact-form-with-multiple-recipients`: `application/x-www-form-urlencoded` params
   - `energy-calculator-contact`: JSON object; set `emailsReceivers: []` to avoid SMTP
5. Injection regression: POST email like `x" OR message LIKE "*ZZZZ*"` — expect success based on **literal** mail only (not a 403 oracle from other fields).
6. Spam threshold: seed ≥5 nodes with the same `mail` via Data Toolbox, then POST that email → `{"success":false,"error":403}`.
7. Happy path under threshold: unique mail + energy-calculator with `emailsReceivers:[]` → `{"success":true,…}`.

### Data Toolbox seed (authenticated browser `fetch`)

```
POST /admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox/_/service/systems.rcd.enonic.datatoolbox/node-create
POST …/property-create  (mail / message String properties)
```

Body is the data object directly (`credentials: 'include'`).

## Pitfalls

- UI reCAPTCHA blocks agent submit on `contact-form-submit`; use service curl.
- Successful POSTs create repo nodes; 1-hour retention cron cleans smtpSent nodes.
- Minimize successful POSTs to submit/new-layout/multiple-recipients (real receivers).

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.gk.k8s.seeds.no` |
| Spam seed mail | `gk535-spam-threshold@example.invalid` |
| Oracle benign mail | `gk535-benign@example.invalid` |
