# How to run xp8migrator and finish an XP 7→8 app upgrade

**Scope:** `_shared`  
**Applies to:** `upgrade-xp-app`  
**Related catalogs:** [xp7-to-xp8-upgrade/](xp7-to-xp8-upgrade/)

## Catalogs (progressive disclosure)

| File | When to read |
|------|----------------|
| [xp7-to-xp8-upgrade/xp7-to-xp8-changes.md](xp7-to-xp8-upgrade/xp7-to-xp8-changes.md) | Breaking changes / diagnosing post-upgrade failures |
| [xp7-to-xp8-upgrade/manual-schemes-migration.md](xp7-to-xp8-upgrade/manual-schemes-migration.md) | Migrator unavailable or reviewing YAML `kind:` output |
| [xp7-to-xp8-upgrade/examples.md](xp7-to-xp8-upgrade/examples.md) | `xplibs.*` aliases, `build.gradle` / TypeScript wiring examples |

Upstream source of truth: <https://raw.githubusercontent.com/enonic/doc-code/refs/heads/master/docs/upgrade.adoc>

## Install Enonic CLI (only after plan approval)

Prefer npm (machine-level tool — leave installed):

```sh
npm install -g @enonic/cli
```

Fallbacks: macOS `brew tap enonic/cli && brew install --no-quarantine enonic`; Linux `sudo snap install enonic`; Windows scoop per <https://developer.enonic.com/docs/enonic-cli/stable/install>. Verify with `enonic --version`.

Always invoke the `use-enonic-cli` skill (and `../../kb/implementation/enonic-cli/`) before running `enonic` commands.

## Non-interactive CLI without deciding for the user

`-f` accepts defaults for every prompt. Never let `-f` choose sandbox, distro version, or whether to start a long-running server. Surface consequential prompts via AskQuestion, then pass explicit flags and use `-f` only to suppress already-answered prompts.

- **`enonic project build -f`** — OK with `-f` (harmless default).
- **`enonic sandbox create`** — confirm version matches app `xpVersion`: `enonic sandbox create <name> -v <xpVersion> -t essentials -f`.
- **`enonic project deploy <sandbox>`** — always name sandbox; use `--skip-start` or detached start (`block_until_ms: 0`) so the agent shell does not hang on a foreground XP server.

## Migrator

Official tool: [`xp8migrator`](https://github.com/enonic/xp8migrator). Run from the app project root after the user approves the plan. Prefer migrator for descriptors; hand-edit only build/TS/code items the migrator does not cover. Delete `./migrator` during cleanup if the plan staged a local copy; never uninstall the Enonic CLI as cleanup.
