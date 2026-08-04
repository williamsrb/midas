# How to optimize agent token usage

**Scope:** `_shared` harness (Cursor + Claude Code)  
**Related:** `How-to-resolve-task-context.md`, rule `token-efficiency-chat.mdc`

## Adopted

| Layer | What | Where |
|-------|------|--------|
| **RTK** | Compact shell tool output (`ls`, `docker ps`, tests, …) | `~/.local/bin/rtk`; Cursor `preToolUse` → `hooks/rtk-cursor.sh`; Claude `PreToolUse` → `hooks/rtk-claude.sh` |
| **Caveman-lite rule** | Terse chat; normal prose for Jira/evidence/PRs/commits | `~/.cursor/rules/token-efficiency-chat.mdc` (mirrored under `~/.claude/rules/`) |
| **Context packages** | Per-skill read allowlists; auto-resolve `<TASK-ID>` | This folder + pipeline skills' Context budget boxes |

## Skipped (do not install)

| Tool | Why |
|------|-----|
| Headroom full wrap/proxy | Invasive; can drop grep/log lines needed for XP/Jira; revisit only with proven Cursor proxy + CCR retrieve |
| pxpipe general proxy | Vision/gist compression; unsafe for exact IDs/paths |
| pxpipe on PRDs | PRDs are contract docs (comment ids, AC); silent confabulation risk |
| Stock Caveman full/ultra always-on | Would poison Jira/evidence client prose |

## Expected savings

Meaningful on noisy shell/log turns; small on total monthly bill. Largest levers remain: **fresh sessions per phase**, thin multitask `DECISIONS.md`, and **not** re-attaching full PRD/plan stacks every step (see allowlists).

## RTK recovery

If a filter hid a needed field:

```bash
RTK_DISABLED=1 <original-command>
# or, when supported by the filter:
rtk <command> --no-compact
```

`git push` stays denied for raw and `rtk`-prefixed forms (`hooks/git-push-policy.sh`).

## Verify

1. Shell `ls` / `docker ps` rewrites toward `rtk …` (Cursor/Claude hooks).
2. `git push` and `rtk git push` still denied.
3. Pipeline skill with only `<TASK-ID>` resolves `prds/` + `plans/` without asking for full paths.
4. Chat stays terse; Jira evidence comments stay professional prose.

## Rollback

Pre-images: `~/.cursor/.token-opt-rollback/<timestamp>/` (+ `CHANGELOG.md`).  
Full backups: `~/backup.cursor.zip`, `~/backup.claude.zip`.
