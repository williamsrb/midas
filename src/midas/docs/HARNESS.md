# The bundled AI harness

Midas ships a curated harness and installs it into this machine's Claude Code and Cursor
setup. Run `midas touch` on a fresh machine to bring it up to the same standard as the
machine the harness was curated on - no Morpheus, no enrollment, no account needed.

## What is in it

Nine kinds of item, each versioned independently:

| Kind | What | Installed to |
|---|---|---|
| `skill` | `midas-*` pipeline adapters + the canonical upstream skills they build on | `~/.cursor/skills`, `~/.claude/skills` |
| `rule` | agent rules (`.mdc`) - git safety, token efficiency, stack conventions | `~/.cursor/rules`, `~/.claude/rules` |
| `hook` | tool hooks - git-push denial, RTK output compaction, history logging | `~/.cursor/hooks` |
| `agent` | subagent definitions | `~/.claude/agents` |
| `command` | slash commands | `~/.cursor/commands`, `~/.claude/commands` |
| `kb` | knowledge base - the "How" half of every skill | `~/.cursor/kb`, `~/.claude/kb` |
| `quality-gate` | the standards validation holds to | `~/.cursor/kb/validation` |
| `mcp` | MCP server template, secrets templated | `~/.config/midas/mcp.json` (0600) |
| `cli` | external tools (`rtk`) - recipe and probe, not the binary | per the item's recipe |

`midas touch` shows the counts and the plan before writing anything; `--dry-run` stops
after the plan.

## Versions

An item's version is the sha256 of its content. The harness version is the sha256 over
every item's digest, sorted - so the same content always produces the same version on any
machine, with no timestamps involved. `MANIFEST.toml` in the package records it;
`midas harness reindex` regenerates it after changing a bundled file.

## Mandatory items and being outdated

Some items are **mandatory**: they change correctness or safety rather than merely
improving things. The git-push-denying hook, the delivery-scope quality gate, and the
context-resolution knowledge-base entry that every skill's context budget delegates to are
mandatory. Agent definitions and `rtk` are not.

- Missing an **optional** item is `behind`. That is a choice, and nothing nags you.
- Missing a **mandatory** item is `outdated`, and it has a cost: every `midas` command
  prints a banner until it is fixed, `midas doctor` fails, and a Morpheus farm ranks this
  client **last** for delegated work - used only when no up-to-date client can take it.

Suppress the banner for one command with `midas --no-warn <cmd>`. Under `--cron` it goes to
the log rather than stdout.

## Applying changes

Nothing is applied unless you ask.

```bash
midas harness status                  # version, currency, missing mandatory items
midas harness list                    # what is available to apply
midas harness apply --mandatory-only  # just the items that carry a cost
midas harness apply --all             # everything
midas harness apply --kind rule       # one kind at a time
midas harness verify                  # re-hash the live tree, probe external tools
midas harness rollback                # restore the previous generation
```

Every apply takes a snapshot first, and five generations are retained.

## The symlink convention is respected

If `~/.claude/skills` is a directory of symlinks into `~/.cursor/skills` - one real copy,
edited from either tool - midas keeps it that way: it writes the payload to the real side
and symlinks the other. It never replaces a symlink with a second, divergent copy, and a
target directory that is itself a symlink (`~/.claude/kb -> ~/.cursor/kb`) is written once,
not twice.

Where no such convention exists, both targets get real content.

## Secrets

**No credential is ever bundled.** The MCP template carries `${VAR}` placeholders, resolved
at install time from the environment or `~/.config/midas/credentials`. The resolved file is
written 0600. An unresolved placeholder is left verbatim so the server fails loudly instead
of silently disabling itself - `midas touch --mcp` names every one it could not fill.

## External items

`rtk` and the 483-file `offline-reference` doc catalogue are declared `external`: midas
carries an install recipe and a verification probe, not the payload. A ~10 MB binary and a
4.7 MB doc tree do not belong in a Python wheel.

External items are verified by **running the probe**, never by trusting the manifest's word
that they are installed. `midas harness verify` reports what it actually found.
