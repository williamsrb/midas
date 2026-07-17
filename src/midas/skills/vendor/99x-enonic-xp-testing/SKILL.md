---
name: 99x-enonic-xp-testing
description: Testing requirements for Enonic XP apps — XP Test Framework (JUnit + JS), Jest with Mock XP (CLIENT and SERVER projects), structure conventions, and verification checklists. Use when changing code under xp/, adding tests, or defining test plans. Installed for Cursor IDE from git.seeds.no/seeds/enonic-skills.
compatibility: Claude Code, Cursor
---

## Cursor IDE

Adapted from [git.seeds.no/seeds/enonic-skills](https://git.seeds.no/seeds/enonic-skills). Run test and build commands via the **Shell** tool from the project root or `xp/` as documented below.

# Enonic XP Testing

## Skill levels (progressive disclosure)

**Level 1:** YAML frontmatter above. **Level 2:** This file. **Level 3:** [REFERENCES.md](REFERENCES.md) — Gradle/JS examples, Jest setup notes, manual test plan template, extended checklist.

## Rule

Changes under `xp/` **must** add or update automated tests **or** ship a concrete manual test plan. High-risk areas (SOAP, id providers, jobs/listeners, services, processors) need broader negative and edge coverage.

## When this skill applies

- Edits under `xp/src/main/resources/`
- New or changed processors, services, controllers, or libs in the XP app
- Changes to React components (prototype-origin or XP-native)
- `xp/build.gradle` includes `com.enonic.xp:testing` and/or Jest / mock-xp

## Step 0 — Verify test infrastructure (mandatory before writing tests)

Before writing any test, validate that the test infrastructure is functional:

1. **Run a dry-run:** `npx jest --selectProjects SERVER --no-coverage` (or CLIENT) from `xp/`.
   It should exit 0 with "No tests found" — not a configuration error.
2. **If it fails**, check these known issues:
   - **Missing `xp/src/main/resources/tsconfig.json`:** The server test tsconfig extends this file. It must exist and provide base compiler options (jsx, moduleResolution, paths for `/lib/enonic/*`, `/lib/xp/*`, `/*`).
   - **Missing `moduleNameMapper` in `jest.config.ts`:** The SERVER project needs a catch-all mapper `'^/(?!lib/xp/|lib/enonic/)(.*)$'` → `<rootDir>/src/main/resources/$1` to resolve absolute imports. XP runtime libraries (`/lib/xp/*`, `/lib/enonic/*`) are type-only packages and must be excluded — they are mocked with `{ virtual: true }` in tests.
   - **Missing `paths` in server tsconfig:** `/lib/enonic/react4xp`, `/lib/enonic/asset`, and `/lib/xp/*` must all be mapped to their `@enonic-types` packages in `compilerOptions.paths`. TypeScript `paths` are fully replaced (not merged) when a child tsconfig overrides them.
   - **Do NOT add `"jest"` to server tsconfig `types`:** `@types/jest` is typically not installed in these projects. Instead, use explicit imports from `@jest/globals` in every test file (see Server-side tests section below).
3. **If infrastructure files need to be created or fixed**, do so before proceeding to write tests.
4. **Verify the fix** by re-running the dry-run command.

## Choose a framework

| Scenario | Prefer |
|----------|--------|
| XP APIs with runtime fidelity (content repo, indexing, auth context) | XP Test Framework |
| Pure logic, fast loop | Jest |
| DOM / browser-like | Jest + jsdom |
| Prototype React components | Jest + jsdom (CLIENT project) |

Both may coexist; Gradle can depend on `npm test`. Details: [REFERENCES.md](REFERENCES.md).

## Option 1: XP Test Framework (JUnit + JavaScript)

Runs JavaScript tests inside an embedded XP runtime via JUnit. Best for services, controllers, and code that needs real XP APIs.

**Gradle dependency** (requires Enonic's Maven repo):

```gradle
repositories {
    mavenCentral()
    maven { url 'https://repo.enonic.com/public' }
}

dependencies {
    testImplementation "com.enonic.xp:testing:${xpVersion}"
}
```

**Layout:**
- JS tests: `xp/src/test/resources/` (mirror main layout, e.g. `lib/foo-test.js`)
- Java bootstrap: `xp/src/test/java/` — class extending `ScriptRunnerSupport`, returns path to JS test

**Run:** `./gradlew test` from `xp/`.

Full examples and mocking patterns: [REFERENCES.md](REFERENCES.md).

## Option 2: Jest (current project setup)

This project uses **Jest** with two projects configured in `xp/jest.config.ts`:

| Project | Environment | Test location | Use for |
|---------|-------------|---------------|---------|
| **SERVER** | `node` | `xp/src/jest/server/**/*.{spec,test}.{ts,tsx}` | Processors, libs, services, pure logic |
| **CLIENT** | `jsdom` | `xp/src/jest/client/**/*.{spec,test}.{ts,tsx}` | React components, DOM interactions |

### Running tests

```bash
# Inside the Docker container (via make access), from xp/:
npm test                           # all projects (also runs via ./gradlew test)
npx jest --selectProjects SERVER   # server tests only
npx jest --selectProjects CLIENT   # client tests only
```

Do **not** use `npx jest --projects <path>` — it overrides project isolation and causes cross-project parse failures.

Gradle integration: `test.dependsOn npmTest` in `build.gradle`, so `make build` runs tests automatically.

### Server-side tests

- Place tests in `xp/src/jest/server/` mirroring the main resources structure.
- The `setupFile.ts` provides `globalThis.log` (debug, info, error, warning) and `globalThis.app`.
- **Always import Jest globals explicitly** from `@jest/globals` instead of relying on global `jest`, `describe`, `it`, `expect`, `beforeEach` etc. The `@types/jest` package is typically not installed, so global Jest types are unavailable. `@jest/globals` is a transitive dependency of Jest and is always available:
  ```typescript
  import { jest, describe, it, expect, beforeEach } from '@jest/globals';
  ```
  This applies to `jest.fn()`, `jest.mock()`, `jest.Mock` type casts, and all test lifecycle functions.
- Path aliases in `tsconfig.json`: `/lib/xp/*` maps to `@enonic-types/lib-*`, `/lib/enonic/*` maps to `@enonic-types/lib-*`, `/*` maps to `src/main/resources/*`.
- **Mocking XP runtime libraries:** `/lib/xp/*` and `/lib/enonic/*` are type-only packages with no JS entry point. Always use `{ virtual: true }` when mocking them:
  ```typescript
  jest.mock('/lib/enonic/react4xp', () => ({
      processHtml: jest.fn(({ value }: { value: string }) => ({ processedHtml: value })),
  }), { virtual: true });
  ```
- **Mocking project modules:** `/lib/99x/modules/*` and other project-internal paths resolve to real files via `moduleNameMapper`. Mock them normally (no `{ virtual: true }`):
  ```typescript
  jest.mock('/lib/99x/extension/portal', () => ({
      myImageUrl: jest.fn(() => ({ link: 'https://example.com/img.jpg' })),
  }));
  ```
- For richer XP API mocking, use `@enonic/mock-xp` (provides `Server`, `LibContent`, `LibPortal`, `LibNode` classes).

### Client-side tests (React / prototype components)

- Place tests in `xp/src/jest/client/`.
- **Always import from the copied prototype location** (`xp/src/main/resources/react4xp/components/prototype/`), never from `../../prototype/` — it is inaccessible in Docker/CI.
- Tests require `make copyComponents` (or `make full`) to have run first so the copied files exist.
- **React 19** requires `globalThis.IS_REACT_ACT_ENVIRONMENT = true` at the top of each test file for `act()` to work.
- SCSS/CSS imports are stubbed via `moduleNameMapper` in `jest.config.ts`.
- Path alias: `/assets/*` maps to `src/main/resources/assets/*`.

## Manual plan (if automation is not feasible)

Include: affected modules/endpoints, happy path, failure path, auth if relevant, data side effects, rollback/safety notes.

## Verification checklist (short)

- Shape of responses / status codes / content-type
- Auth: anonymous vs roles
- Data effects: content and repo
- Edges: empty input, bad ids, missing config
- High-risk: errors, timeouts, idempotency where needed

Full table and examples: [REFERENCES.md](REFERENCES.md).
