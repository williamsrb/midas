# How to debug XP server logs and build failures

**Scope:** `_shared` (Enonic XP 7/8 apps)  
**Applies to:** `debug-xp-app` and any skill diagnosing Gradle/TS build or `server.log` runtime errors  
**Related:** `use-enonic-cli` skill; `../../kb/implementation/enonic-cli/README.md`

## Log file locations

| Log | Typical path | Contains |
|-----|--------------|----------|
| Server log | `$XP_HOME/logs/server.log` | Runtime errors, Nashorn stack traces, app lifecycle |
| Build output | Terminal / Gradle console | Compilation errors, dependency issues |
| Sandbox log | `~/.enonic/sandboxes/<name>/home/logs/server.log` | Same as server log, sandbox-specific |

`$XP_HOME` is usually `~/.enonic/sandboxes/<name>/home` when running via CLI sandbox.

## Source file mapping

| Error references | Check source at | Check compiled at |
|------------------|-----------------|-------------------|
| `.js` controller | `src/main/resources/**/<name>.ts` or `.js` | `build/resources/main/**/<name>.js` |
| `.xml` descriptor | `src/main/resources/**/<name>.xml` | Same (copied as-is) |
| Java class (XP internals) | `https://github.com/enonic/xp` via `gh` | N/A |
| `node_modules` / lib path | `build.gradle` dependencies | `build/resources/main/lib/` |

Compiled JS under `build/resources/main/` is runtime truth for Nashorn errors — then map back to source.

## Reading large logs

When `server.log` is large (>500 lines), use a Task subagent (`subagent_type: shell`) — do not load the full file in the main context:

```text
tail -1000 $XP_HOME/logs/server.log | grep -E 'ERROR|WARN|Exception|at ' --context=3
```

Return only ERROR/WARN blocks with surrounding context.

If the user says the app does not load and grepping the app name in `server.log` yields zero matches, the app was never seen by XP (deploy path mismatch), not an in-app error.

## Server-side logging

The global `log` object (`log.info`, `log.error`, `log.warning`, `log.debug`) — no `console.log` on the server. Format strings use `%s`.

```js
log.info('Debug: value = %s', JSON.stringify(value));
log.error('Failed at step: %s', stepName);
```

## Deployment while debugging

1. Prefer project `CLAUDE.md` / `README` / Makefile.
2. Prefer Enonic CLI: `enonic project deploy` / `enonic sandbox list` (see `use-enonic-cli` + enonic-cli KB).
3. Fall back to `./gradlew deploy` only if CLI is unavailable.
4. After deploy: `tail -f $XP_HOME/logs/server.log`.
5. **Always ask before deploying.**

## Sibling repos

Before deep-diving one app: `ls ..` for related apps/libs that may own the failure.

## Domain knowledge hand-off

| Topic | Where |
|-------|-------|
| Controllers, services, schemas | `develop-xp7-backend` |
| React4XP | `develop-react4xp-v6` / `develop-react4xp-v7` |
| CLI | `use-enonic-cli` + this KB folder’s sibling `enonic-cli/` |
