# How to test Enonic admin su/password login on NTF hosts

**Scope:** `ntf`  
**Applies to:** review and club staging (`https://{host}.ntf.seeds.no/`)  
**Related:** NTF-1218

## Purpose

Verify that default Enonic XP superuser credentials (`su` / `password`) are **rejected** at the admin login page. This validates the ops acceptance criterion: `xp.suPassword` rotated in deployed environments.

## Host list derivation

```bash
# Review + league alias + 57 club IDs
echo review norsk-toppfotball
grep -h 'exports.club_id' clubs/*/src/main/resources/lib/config/local.js \
  | sed "s/.*= \"//;s/\";//" | sort -u
```

URL pattern: `https://{host}.ntf.seeds.no/admin/tool`

League alias `norsk-toppfotball` comes from `custom_staging_url` in `football/src/main/resources/lib/config/global.js`.

**Out of scope:** production (`*.fotball.seeds.no`, `ntf-*.enonic.cloud`).

## Reachability gate

Probe each host before login testing:

```bash
curl -sS -L --max-time 15 -o /tmp/body.html -w "HTTP %{http_code}\n" \
  "https://{host}.ntf.seeds.no/admin/tool"
grep -q "Enonic XP - Login" /tmp/body.html && echo REACHABLE || echo UNREACHABLE
```

| Result | Criteria |
|--------|----------|
| **REACHABLE** | HTTP 401 (or redirect) with `Enonic XP - Login` in body |
| **UNREACHABLE** | Timeout, DNS, SSL fatal, 502/503, or no login page → skip |

## Login test

**Credentials:** `su` / `password`  
**Target:** `/admin/tool`

### Pass (security good)

- Login form shows username `su` filled
- Error message **Login failed!** (`notify.login.failed`) after submit
- Admin tool launcher **not** visible

### Fail (critical — escalate)

- Login accepted
- Admin launcher / Content Studio / Applications visible

### Browser selectors (Enonic XP login page)

| Element | Selector |
|---------|----------|
| Username | `#username-input` |
| Password | `#password-input` |
| Submit | `#login-button` or Enter on password field |
| Error message | `#message-container` |

### Manual browser steps

1. Navigate to `https://{host}.ntf.seeds.no/admin/tool`
2. Confirm title **Enonic XP - Login**
3. Fill `su` / `password`, submit
4. Confirm **Login failed!** (not admin UI)
5. Screenshot → `su-login-fail-{host}.png`

### Playwright one-liner (batch)

```bash
# Requires: npm install playwright && npx playwright install chromium
node /path/to/ntf1218-login-test.mjs
```

## Post-processing

```bash
mogrify -background white -alpha remove ~/.cursor/prds/NTF-1218/evidence/su-login-test/*.png
```

## Sample data

| Field | Example |
|-------|---------|
| Review host | `https://review.ntf.seeds.no/admin/tool` |
| Club host | `https://rbk.ntf.seeds.no/admin/tool` |
| Credentials | `su` / `password` |
| Pass signal | `Login failed!` |
| Fail signal | Admin launcher visible |

## Pitfalls

- Most club staging hosts are **unreachable** (timeout/502) — only test hosts that pass the curl gate
- `browser-ide-browser` MCP may be unavailable; use Playwright headless as fallback
- Jira screenshot upload is manual; use `[ATTACH: su-login-fail-{host}.png]` placeholders in comment drafts
- Do not test production hosts unless explicitly scoped

## Evidence paths

| Artifact | Path |
|----------|------|
| Reachability report | `~/.cursor/prds/NTF-1218/evidence/su-login-test/reachability-report.txt` |
| Screenshots | `~/.cursor/prds/NTF-1218/evidence/su-login-test/su-login-fail-*.png` |
| Comment draft | `~/.cursor/prds/NTF-1218/evidence-comment-su-login-draft.md` |
