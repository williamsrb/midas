# Enonic CLI — operational knowledge base

**Scope:** `_shared`  
**Applies to:** `use-enonic-cli`, `upgrade-xp-app`, `debug-xp-app`, sandbox/deploy workflows  
**CLI version baseline:** 4.0.0 (verify with `enonic --version`)

Skill `use-enonic-cli` owns **critical rules** (always `-f` when accepted, local vs remote, port 4848, XP 8 default). This folder owns command catalogs and recipes.

| File | Content |
|------|---------|
| [commands.md](commands.md) | Full flag tables for every command |
| [auth-and-env.md](auth-and-env.md) | Auth methods, env vars, ports, CI/CD patterns |
| [workflows.md](workflows.md) | Multi-step recipes |

## Command syntax

```
enonic <group> <action> [positional-args] [flags]
```

Groups: `project`, `sandbox`, `snapshot`, `dump`, `app`, `repo`, `cms`, `system`, `auditlog`, `cloud`.  
Standalone: `create`, `dev`, `export`, `import`, `vacuum`, `latest`, `upgrade`, `uninstall`.

## Auth flags (remote) — summary

| Method | Flags | When |
|--------|-------|------|
| Basic auth | `-a user:password` | XP < 7.15 or quick local testing |
| Service account key | `--cred-file path/to/key.json` | XP 7.15+ / CI/CD (preferred) |
| Mutual TLS | `--client-cert` + `--client-key` | Zero-trust |

Priority: flags → environment variables → no auth. Details: [auth-and-env.md](auth-and-env.md).

## Common patterns

```bash
enonic project create my-app -r starter-vanilla -s my-sandbox -f
ENONIC_CLI_REMOTE_URL="server:4848" enonic project install -a su:password -f
enonic export -t site-backup --path cms-repo:draft:/content/my-site -a su:password -f
enonic dump create -d nightly --skip-versions -a su:password -f
enonic repo reindex -r cms-repo -b draft,master -i -a su:password -f
enonic vacuum -b -t P30D -a su:password -f
enonic auditlog cleanup --age P90D -a su:password -f
```

## File locations

| Item | Path |
|------|------|
| CLI home | `~/.enonic/` |
| Sandboxes | `~/.enonic/sandboxes/<name>/` |
| Dumps / exports | `$XP_HOME/data/dump/` / `$XP_HOME/data/export/` |
| Project config | `<project-root>/.enonic` |

For abbreviated group tables (project, sandbox, dump, …), prefer [commands.md](commands.md) over reconstructing from memory.
