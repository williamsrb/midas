---
name: test-xp-apps
aliases: enonic-xp-testing, xp-testing, enonic-testing
description: Testing requirements for Enonic XP apps — XP Test Framework (JUnit + JS), Jest with Mock XP (CLIENT and SERVER projects), structure conventions, and verification checklists. Use when changing code under xp/, adding tests, or defining test plans. Installed for Cursor IDE from git.seeds.no/seeds/enonic-skills.
compatibility: Claude Code, Cursor
---

## Cursor IDE

Adapted from [git.seeds.no/seeds/enonic-skills](https://git.seeds.no/seeds/enonic-skills). Run test and build commands via **Shell** from the project root or `xp/` as documented in the KB.

# Enonic XP Testing

## Knowledge base (mandatory How)

Gradle/JS examples, Jest setup notes, mocking patterns, manual plan template, extended checklist:

`../../kb/testing/_shared/How-to-test-enonic-xp-apps.md`

This skill owns **when** tests are required, framework choice, Step 0 gate, and the short verification checklist.

## Rule

Changes under `xp/` **must** add or update automated tests **or** ship a concrete manual test plan. High-risk areas (SOAP, id providers, jobs/listeners, services, processors) need broader negative and edge coverage.

## When this skill applies

- Edits under `xp/src/main/resources/`
- New or changed processors, services, controllers, or libs in the XP app
- Changes to React components (prototype-origin or XP-native)
- `xp/build.gradle` includes `com.enonic.xp:testing` and/or Jest / mock-xp

## Step 0 — Verify test infrastructure (mandatory before writing tests)

Before writing any test, validate that the test infrastructure is functional:

1. **Dry-run:** `npx jest --selectProjects SERVER --no-coverage` (or CLIENT) from `xp/` — exit 0 with "No tests found", not a config error.
2. **If it fails**, check known issues in the KB How-to (missing `xp/src/main/resources/tsconfig.json`, `moduleNameMapper`, paths, never add `"jest"` to server tsconfig `types`).
3. Fix infrastructure before writing tests; re-run the dry-run.

## Choose a framework

| Scenario | Prefer |
|----------|--------|
| XP APIs with runtime fidelity | XP Test Framework |
| Pure logic, fast loop | Jest |
| DOM / browser-like / prototype React | Jest + jsdom (CLIENT) |

Both may coexist. Details: KB How-to.

## Option 1: XP Test Framework (summary)

Embedded XP runtime via JUnit. Dependency `com.enonic.xp:testing:${xpVersion}` + Enonic Maven repo. JS tests under `xp/src/test/resources/`; Java bootstrap extends `ScriptRunnerSupport`. Run: `./gradlew test` from `xp/`. Full examples: KB.

## Option 2: Jest (summary)

| Project | Env | Location |
|---------|-----|----------|
| **SERVER** | `node` | `xp/src/jest/server/**/*.{spec,test}.{ts,tsx}` |
| **CLIENT** | `jsdom` | `xp/src/jest/client/**/*.{spec,test}.{ts,tsx}` |

```bash
# Inside Docker (make access), from xp/:
npm test
npx jest --selectProjects SERVER
npx jest --selectProjects CLIENT
```

Do **not** use `npx jest --projects <path>`. Always import from `@jest/globals`. Mock `/lib/xp/*` and `/lib/enonic/*` with `{ virtual: true }`. CLIENT imports from copied prototype under `xp/src/main/resources/react4xp/components/prototype/` after `make copyComponents`. Full patterns: KB.

## Manual plan (if automation is not feasible)

Include: affected modules/endpoints, happy path, failure path, auth if relevant, data side effects, rollback/safety notes.

## Verification checklist (short)

- Shape of responses / status codes / content-type
- Auth: anonymous vs roles
- Data effects: content and repo
- Edges: empty input, bad ids, missing config
- High-risk: errors, timeouts, idempotency where needed

Full table: KB How-to.
