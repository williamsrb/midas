# How to clean orphaned site-config editor refs (vet)

**Scope:** `vet`  
**Applies to:** review / staging with layers (`norsk` + `english`)  
**Related:** VET-1195, VET-1136, VET-930

## Prerequisites

- XP admin session (`/admin/tool`)
- App deployed with service `cleanOrphanedSiteRefs`

## Procedure

1. Dry-run (admin browser or curl with session cookie):  
   `https://<host>/_/service/com.vetinst/cleanOrphanedSiteRefs`  
   Expect JSON `repos[].checked` listing paths with `editor` / `chiefEditor` / `cookies`, or empty if already clean.
2. Optional broader scan: add `?scanAll=true`.
3. Apply + publish: `?apply=true` (publish default on).
4. Verify in Data Toolbox: open English `/eng` and Norwegian `/vetinst` site nodes → `data` has no orphaned reference properties.
5. Content Studio: edit `/eng` frontpage → Publish wizard — Asle Haukaas / Johanne Bergstrøm Sundell must not appear solely from site-config refs.
6. Large remaining dependency counts under `/vetinst/...` marked New are expected layer-inheritance noise during VET-997 migration (not fixed by this cleanup).

## Pitfalls

- Anonymous call returns **403** (admin-only).
- Do not remove `footerRightText` — intentional HtmlArea replacement for the old editor fields.
- Public English marketing path may be `/en`; CMS layer/site path remains `/eng`.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.vet.k8s.seeds.no` |
| Dry-run | `/_/service/com.vetinst/cleanOrphanedSiteRefs` |
| Apply | `/_/service/com.vetinst/cleanOrphanedSiteRefs?apply=true` |
