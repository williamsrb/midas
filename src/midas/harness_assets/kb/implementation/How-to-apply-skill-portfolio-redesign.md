# How to apply skill-portfolio redesign phases

**Scope:** `_shared`  
**Applies to:** personal `~/.cursor/skills` maintenance  
**Related:** `~/.cursor/plans/skill-portfolio-redesign.md`

## Prerequisites

- Backup under `~/.cursor/skills-backup-*/` (never `rm` skills — `mv` to displaced).
- Plan path: `~/.cursor/plans/skill-portfolio-redesign.md`.

## Procedure

1. Phase 1 — write routing How-To under `~/.cursor/kb/implementation/`.
2. Phase 2 — evolve `qa-validation` modes; displace `task-review` real dir; symlink `task-review` → `qa-validation`; copy Codex script + review template into `qa-validation/`.
3. Phase 3 — extend `run-plan` execution rules for implementation / evidence / validation delegation.
4. Phase 4 — **do not** binary-merge enonic/generic staged-validation yet; add validation KB routing How-To + description cross-links.
5. Phase 5 — move bulky upgrader “What changes” into `references/xp7-to-xp8-changes.md`.
6. Skip Phase 6–7 until user decides worklogs archive and audit date.

## Pitfalls

- Alias chains (`review-task` → `task-review` → `qa-validation`) must keep resolving after displace.
- Full staged-validation merge is higher risk — defer until profiles are designed.
