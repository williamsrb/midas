# How to find Vis alle / Show all list pages (vet)

**Scope:** `vet`  
**Applies to:** review (`https://review.vet.k8s.seeds.no`)  
**Related:** VET-1202

## Prerequisites

- Public site access (no admin for employee/species pages)

## Procedure

1. Find employees with long related lists via  
   `GET /ansatte/_/service/com.vetinst/employeeInfiniteScroll?page=1&count=50`
2. Open `/ansatte/<slug>` and search HTML for `data-relationship-list-expand` / `Vis alle`.
3. Strong examples found on review:
   - list-relationship: `/ansatte/anne-bang-nordstoga` (Vitenskapelige artikler)
   - reverse-relation + list-relationship: `/ansatte/anne-margrete-urdahl` (Rapporter + artikler)
   - reverse-relation on species: `/dyr/fjorfe` (multiple lists; hidden items present)
4. English labels: use header language switcher → `/en/staff/<slug>` (not `/eng/staff/...`).
5. Confirm caps in browser console/DOM:
   - visible `li` without `.displayNone`
   - hidden `.displayNone` count
   - expand control label text

## Pitfalls

- `/eng/staff` infinite-scroll employee URLs may return “Out of scope”; prefer `/en/staff/<slug>` from the Norsk→English switcher.
- Tall pages: scroll `[data-relationship-list-expand]` into view before screenshotting.
- Empty Antall on list-children shows all children and **no** Vis alle (e.g. `/dyr`).

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.vet.k8s.seeds.no` |
| NO employee | `/ansatte/anne-margrete-urdahl` |
| EN employee | `/en/staff/anne-margrete-urdahl` |
