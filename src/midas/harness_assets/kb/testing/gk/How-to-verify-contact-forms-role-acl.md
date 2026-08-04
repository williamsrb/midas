# How to verify contact-forms role ACL (gk)

> **Deprecated for GK-535 DoD (analyst comment 518119):** Custom `role:gk.contact-forms` was reverted. Keep this file only for historical review envs that still have the leftover role. For current spam/injection tests use [How to test contact-form submit services](./How-to-test-contact-form-services.md) (admin connect; no role ACL required).

**Scope:** `gk`  
**Applies to:** review / staging with XP admin (legacy only)  
**Related:** [How to test contact-form submit services](./How-to-test-contact-form-services.md)

## Prerequisites

- Logged-in XP admin (`/admin`)
- Data Toolbox: `<base>/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox`
- Users app: `<base>/admin/tool/com.enonic.xp.app.users/main`

## Procedure

1. Users → search `gk.contact-forms` → expect role `/roles/gk.contact-forms`.
2. Data Toolbox → Node Tree → confirm repos:
   - `contact-forms-repo`
   - `contact-forms-repo-with-multiple-recipients`
   - `contact-forms-energy-calculator`
3. Open root permissions (`#permissions?repo=<repo>&branch=master&path=%2F`) → expect `role:gk.contact-forms` with READ/CREATE/MODIFY/DELETE.
4. Open a **child** node permissions (not only root). If children show only `system.admin` / `system.everyone`, spam counts via `role:gk.contact-forms` will miss them.
5. Fix when needed: edit root permissions → enable **Overwrite child permissions** → APPLY (Data Toolbox `permission-apply`). Or re-deploy after bootstrap always re-applies child ACLs.
6. Services URL used by toolbox (authenticated browser session):  
   `/admin/tool/systems.rcd.enonic.datatoolbox/data-toolbox/_/service/systems.rcd.enonic.datatoolbox/{node-create|property-create|permission-apply|permission-list|node-query|task-get}`  
   POST JSON body is the `data` object directly (not wrapped again).

## Pitfalls

- Root can look correct while children are still invisible to the limited role (migration flag `contactFormsRoleApplied` used to skip re-apply).
- Seeded nodes for spam tests must include the role in ACL before trusting a 403.

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.gk.k8s.seeds.no` |
| Role | `role:gk.contact-forms` |
| Seed path | `/gk535-spam-1` |
