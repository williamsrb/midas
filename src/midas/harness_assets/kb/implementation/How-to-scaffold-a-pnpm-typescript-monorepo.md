# Scaffolding a pnpm + TypeScript monorepo that shells out to agent CLIs

**Scope:** `_shared` (any pnpm 11 / Node 22 / TS 5.9 workspace)
**Applies to:** new multi-package repos, especially ones that spawn `claude` / `cursor-agent` / other CLIs
**Related:** plan `~/.cursor/plans/morpheus-implementation-spec.md`; built at `~/Workspace/Automated/morpheus`
**Verified:** 2026-07-31 — node 22.15.1, corepack 0.32.0, pnpm 11.18.0, zod 4.4.3, vitest 4.1.10

## Layout that works

```text
package.json            # private, "type": "module", packageManager: pnpm@X, engines.node
pnpm-workspace.yaml     # packages: apps/*, packages/*
tsconfig.base.json      # compilerOptions only
tsconfig.json           # extends base; paths → each package's src/index.ts
vitest.config.ts        # resolve.alias → the same src/index.ts paths
packages/<lib>/package.json   # main/types/exports all point at ./src/index.ts
```

Point `exports` at `src/index.ts` (not `dist/`) for internal workspace packages: `tsx` and
`vitest` then run straight from source, and there is no build step to keep in sync during
development. Only the app that ships (e.g. the web bundle) needs a real build.

`tsconfig.json` `paths` and `vitest.config.ts` `resolve.alias` must list the same mappings —
they are read by different tools and neither falls back to the other.

## Pitfalls

### A CLI dependency's bin only exists in the package that declares it

pnpm's isolated `node_modules` puts an executable in the `node_modules/.bin` of the package
whose `package.json` lists the dependency — **not** at the repo root. So this fails:

```ts
// walks up from cwd looking for node_modules/.bin/<tool> — never finds it
let dir = resolve(process.cwd());
```

Two rules:

1. Declare the dependency in the package that actually shells out to it, not in the app that
   happens to expose the feature.
2. Resolve from the module's own location as well as the caller's cwd:

```ts
const bin =
  (await binAbove(searchFrom)) ??
  (await binAbove(dirname(fileURLToPath(import.meta.url)))) ??
  (await whichBinary(tool));
```

Symptom: a `doctor`-style check reports "not resolved" while `pnpm --filter <app> exec <tool>`
works fine. That difference *is* the diagnosis.

### zod 4: `.default({})` on a nested object breaks the inferred type

`z.object({...}).default({})` no longer typechecks in zod 4 when the inner object has required
keys with defaults — `tsc` reports TS2769 "No overload matches this call". Use `.prefault({})`,
which applies the default **before** parsing so the inner defaults still run:

```ts
claude: z.object({ enabled: z.boolean().default(true), bin: z.string().default('claude') }).prefault({}),
```

### `new Request(url, { headers: {...}, ...init })` silently drops the headers

Object spread order decides the winner. If `init` carries its own `headers`, spreading it last
replaces the merged object — including whatever the helper added (a `host` header, an auth
token). Every test using the helper *without* extra headers passes, so the failures look
unrelated to the helper. Put `...init` first:

```ts
new Request(url, { ...init, headers: { host: '127.0.0.1:7420', ...(init.headers ?? {}) } });
```

### pnpm 11 blocks install scripts until you allow them

The first `pnpm install` stops with `allowBuilds: esbuild: set this to true or false` written
into `pnpm-workspace.yaml`. It is a prompt, not an error — set the value and re-run:

```yaml
allowBuilds:
  esbuild: true   # vite/tsx bundle esbuild; its install script links the platform binary
```

`minimumReleaseAgeExclude` is the companion knob when a pinned version is newer than the
configured cool-off window.

### Top-level `await` in a scratch `.ts` script

`tsx foo.ts` transforms as CJS and fails with "Top-level await is currently not supported with
the cjs output format". Name throwaway scripts `.mts`.

### npm scripts that point at files nobody wrote

A scaffold generated from a plan will happily contain `"doctor": "node scripts/doctor.mjs"`
with no `scripts/` directory. Run every script in `package.json` once before calling the
scaffold done — `pnpm run <name>` for each — because typecheck and tests do not touch them.
