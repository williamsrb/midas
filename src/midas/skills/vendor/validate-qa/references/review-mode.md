# QA review mode (artifact)

Use when `validate-qa` runs in **review mode** (`qa-review` / `review-task`, or the user asks for a written review file).

Apply shared delivery standards from `../../../kb/validation/Quality-gate-*.md`.

## Extra steps (after core QA checks)

1. Resolve issue key from user or nearest `.tasks/<ISSUE-KEY>.md` / `tasks/<ISSUE-KEY>.md`.
2. Read the task spec fully when present.
3. Prefer **less aggressive auto-fix** unless the user asked to fix — report first, fix Blockers when safe.
4. Standards extras (Enonic React4XP): when relevant, read `apply-react4xp-practices` and note violations in the artifact.
5. Optional Impeccable (design / frontend UI only): when the delivery is clearly UI/design-related, consult the `impeccable` skill and/or `impeccable detect` on changed UI paths; record material findings in the artifact as Notes/Concerns (not a mandatory redesign). Skip for non-UI deliveries.
6. Optional build gates (React4XP projects) — record failures as CRITICAL in the artifact:
   - `npx tsc --noEmit -p xp/tsconfig.xp.nashorn.json`
   - `npx tsc --noEmit -p xp/tsconfig.react4xp.json`
   - `cd xp && npx jest --no-coverage`
   - `make build` only if Docker/available; do not `make deploy`
7. Write `tasks/<ISSUE-KEY>-review.md` or `.tasks/<ISSUE-KEY>-review.md` from [assets/review-artifact-template.md](../assets/review-artifact-template.md).
