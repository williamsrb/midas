# How to search via Data Toolbox (Enonic XP)

**Scope:** `_shared`  
**Applies to:** any XP review/staging host with Data Toolbox installed  
**Related:** project-specific public URL mapping (e.g. vet NO/EN bases below)

## Prerequisites

- Logged-in XP admin session (`/admin`)
- Tool URL:
  - XP 7 / classic: `<base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox`
  - XP 8: `<base>/admin/systems.rcd.enonic.datatoolbox/data-toolbox` (**no** `/tool/` — classic path 404s)

## Procedure

1. Open **Node Search** in Data Toolbox.
2. Leave repositories/branches as needed (often “All”).
3. Put a NoQL query in the **Query** field (or use the `#search?query=` URL fragment).
4. Click **Search** and read result rows (`name`, `repo:branch:path`, score).
5. Map content `_path` to a public site URL (strip `/content/<site-name>` and apply the host’s language base — see sample data).
6. Prefer **master** hits for live evidence; skip `_templates` and archive unless testing those.

### Common part lookup

Find pages that use a part descriptor:

```
components.part.descriptor LIKE '*:grid'
```

URL-encoded example:

```
# XP 8:
<base>/admin/systems.rcd.enonic.datatoolbox/data-toolbox#search?query=components.part.descriptor%20LIKE%20'*%3Agrid'&sort=_score%20DESC
# XP 7 / classic (has /tool/):
<base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox#search?query=components.part.descriptor%20LIKE%20'*%3Agrid'&sort=_score%20DESC
```

Other patterns:

| Goal | Query |
|------|--------|
| Layout | `components.layout.descriptor LIKE '*:my-layout'` |
| Page controller | `components.page.descriptor LIKE '*:my-page'` |
| Content type | `type = 'com.example.app:my-type'` |

### Narrowing results

```
components.part.descriptor LIKE '*:grid' AND _path LIKE '/content/vetinst/*' AND _path NOT LIKE '*/_templates/*'
```

## Pitfalls

- Hash-route `#search?query=...` needs an authenticated admin session; unauthenticated opens login.
- Draft vs master duplicates appear as separate hits — use master for public evidence.
- English public paths are not always the same as content `_path` segments (e.g. `dyr` vs `animals`).

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL (vet NO) | `https://review.vet.k8s.seeds.no` |
| Base URL (vet EN) | `https://review.vet.k8s.seeds.no/en/` |
| Part query | `components.part.descriptor LIKE '*:grid'` |
| NO content → public | `/content/vetinst/dyr/oppdrettsfisk` → `/dyr/oppdrettsfisk` |
| EN content → public | `/content/vetinst/animals/oppdrettsfisk` → `/en/animals/oppdrettsfisk` |
