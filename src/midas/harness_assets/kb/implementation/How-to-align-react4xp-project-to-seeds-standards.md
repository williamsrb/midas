# How to align a React4XP project to Seeds standards

**Scope:** `_shared` (Seeds Enonic React4XP apps)  
**Applies to:** `set-up-enonic-react4xp` post-bootstrap; also when fixing an existing `xp/` tree to match bootstrap conventions  
**Related:** skill `set-up-enonic-react4xp` (wizard + bootstrap script own greenfield flow)

Skip any step whose target file is missing. Do not overwrite existing custom values unless noted.

## 1 — Disable `@typescript-eslint/no-unused-vars` in ESLint config

- Search under `xp/` for `.eslintrc*`, `eslint.config.js` / `.mjs`.
- If found, set rule `@typescript-eslint/no-unused-vars` to `"off"` (add or update under `rules`).

## 2 — Extend tsup `external` array

- Find `xp/tsup.config.{ts,js,mjs,cjs}`.
- If `external` exists inside `defineConfig`, append when missing:

```text
'/lib/cache',
'/lib/http-client',
'/lib/enonic/static',
'/lib/cron',
'/lib/text-encoding',
'/jobs',
'/lib/99x/modules/default-page',
```

## 3 — Libraries in `xp/build.gradle`

Inside `dependencies`, uncomment or add when absent:

```text
include 'com.enonic.lib:lib-cache:2.2.1'
include "com.enonic.xp:lib-i18n:${xpVersion}"
include "com.enonic.xp:lib-repo:${xpVersion}"
```

## 4 — Exclude `prototype/` from lint and type-checking

**eslint.config.mjs** — add `'**/prototype/**'` to global `ignores` (create `{ ignores: ['**/prototype/**'] }` at top of export if needed).

**tsconfig.react4xp.json** — add `"./src/main/resources/**/prototype/**"` to `exclude`.

**tsconfig.xp.nashorn.json** — add `"src/main/resources/**/prototype/**"` to `exclude`.

## 5 — sass-loader `additionalData` in webpack React4XP config

In `xp/webpack.config.react4xp.js` (or `.ts`/`.cjs`/`.mjs`), on `sass-loader` options:

```js
additionalData: `@use '/react4xp/shared/scss/variables' as *;`
```

If `additionalData` already exists, append the `@use` line (newline-separated); do not overwrite unrelated content.

## 6 — npm dependencies on `xp/package.json`

Add missing packages using versions from the bootstrap skill’s `template/prototype/package.json` (or the project’s prototype package.json when aligning an existing app):

- `dayjs`

Do not overwrite existing entries.
