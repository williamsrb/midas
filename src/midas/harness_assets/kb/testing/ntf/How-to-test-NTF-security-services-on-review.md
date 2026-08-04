# How to test NTF security services on review

**Scope:** `ntf`  
**Applies to:** review (`https://review.ntf.seeds.no/`)  
**Related:** NTF-1217, NTF-1218, NTF-1219, NTF-1220

## Prerequisites

- Review deploys **football** app only (`no.seeds.app.football`) via GitLab CI
- **toppfotball** (`no.toppfotball`) is **not** on review — service URLs return HTTP 303; use GitLab source for toppfotball evidence

## Procedure

### Service URL pattern

```
<base>/_/service/no.seeds.app.football/<service-name>
<base>/_/service/no.toppfotball/<service-name>   # club/league hosts only
```

### NTF-1217 — update-match-events removed

```bash
# Removed endpoint → 404
curl -sS -o /dev/null -w "HTTP %{http_code}\n" -X POST \
  "<base>/_/service/no.seeds.app.football/update-match-events"

# Harness → 410 + JSON
curl -sS "<base>/_/service/no.seeds.app.football/test_requests"
```

### NTF-1220 — send-verification-email auth required

```bash
curl -sS -X POST -D - -o /dev/null -w "HTTP:%{http_code}\n" \
  "<base>/_/service/no.seeds.app.football/ntfpwa-send-verification-email" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "userId=%27%20OR%20%271%27%3D%271&email=attacker@example.com"
# Expect: HTTP 401
```

### NTF-1218 / NTF-1219 — toppfotball shared-content

Verify on GitLab (`review` branch) or a club host where `no.toppfotball` is installed:
- `toppfotball/.../shared-content.xml` — `role:system.authenticated`
- Handlers return 401 when `authLib.getUser()` is null

## Pitfalls

- Do not expect runtime 401 from `no.toppfotball/*` on `review.ntf.seeds.no` — app not deployed there
- `update-match-events` POST may return an HTML 404 page body; status code 404 is the pass signal
- Jira evidence: save drafts locally (`~/.cursor/prds/<KEY>/evidence-comment-draft.md`); post manually

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.ntf.seeds.no/` |
| Injection payload | `userId=' OR '1'='1` |
| GitLab repo | `https://git.seeds.no/seeds/football` branch `review` |
