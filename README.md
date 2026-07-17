# Midas

Automated Jira-to-commit development pipeline. **Linux only** (Ubuntu 24.04+).

Midas watches Jira for tasks assigned to you, downloads them, detects each
project's environment requirements, clones/branches the repository over SSH,
plans the solution with an expensive model (Opus) and implements it with a
mid-tier model (Sonnet) via headless CLI agents — **no LLM API key needed**,
it reuses your `claude` (or `cursor-agent`) subscription login — then
validates, commits on a branch named after the Jira key, and reports for
human validation. `.NET` projects are skipped by policy.

```
crontab (*/15) -> midas run
  ├─ preflight guard (auto-interrupt): internet, disk, ssh-agent,
  │                                    install integrity, agent auth, jira
  ├─ poll Jira (REST token; agent+MCP fallback)
  └─ per-task pipeline (resumable state machine):
     discovered -> fetched -> env_detected -> cloned -> branch_ready
     -> planned(Opus) -> implemented(Sonnet) -> validated -> committed
     -> reported -> awaiting_human      (terminal: skipped_dotnet | blocked)
```

## Install

### From the .deb (system-wide)

```bash
packaging/deb/build-deb.sh            # builds dist/midas_<ver>_all.deb
sudo apt install ./dist/midas_*.deb
```

### User-space (no sudo)

```bash
packaging/install.sh                  # ~/.local/share/midas + ~/.local/bin/midas
```

The user-space installer prefers the newest **pyenv** Python (>= 3.11) when
present, else system `python3`.

### Then, as your normal user

```bash
midas setup      # detects defaults (git identity, claude login, Cursor MCPs)
midas doctor     # run all preflight checks
midas enable     # install the crontab polling entry
```

## Configuration

- `~/.config/midas/config.toml` — everything: ME identities, Jira base URL and
  pickup mode, clone-URL template, models, disk limits, cron interval.
- `~/.config/midas/credentials` — `JIRA_API_TOKEN=...` (chmod 600). Create a
  token at <https://id.atlassian.com/manage-profile/security/api-tokens>.
  Without a token Midas degrades to the agent+MCP fallback (works, but every
  Jira operation costs an LLM call).
- `~/.config/midas/mcp.json` — MCP servers passed to the agent (imported from
  `~/.cursor/mcp.json` at setup).

Task pickup modes (`jira.pickup`):

- `status` (default): `assignee = currentUser() AND status in (...) AND updated >= -2d`
- `label`: only tasks labeled `midas` (safest start).

## Agent providers

Both `claude` and `cursor-agent` are supported, each with **subscription**
auth (reuses your CLI login - no API key) or **api-key** auth (key stored in
the midas credentials file). Choose in `midas setup`; it detects whether you
are logged in and prints the login instructions if not (`claude` + `/login`
choosing the subscription account, or `cursor-agent login`).

## Daily commands

| Command | Purpose |
|---|---|
| `midas run` | one polling cycle (what cron runs) |
| `midas task RFD-123` | force one task through the pipeline now |
| `midas task FAKE-1 --from-file task.md --dry-run` | offline plumbing test |
| `midas list` / `midas status` | queue, disk usage, blocked state |
| `midas logs [--task RFD-123]` | rotating logs under `~/.local/state/midas/logs/` |
| `midas test RFD-123` | run the generated Playwright plan (docker) after the review deploy |
| `midas enable` / `disable` | manage the crontab entry |
| `midas touch` | install midas skills + LLM-usage hooks into Claude/Cursor |
| `midas greed` | harvest useful skills from your workspace into midas |
| `midas usage` | LLM interaction ledger: calls, tokens, cost per model |
| `midas docs [usage\|tokens]` | built-in documentation |

## Token optimization

Midas applies the 10-80-10 orchestration pattern (expensive model plans,
mid-tier executes, cheap `haiku` does glue work), terse-output rules on every
prompt, a thinking-effort cap (`agents.effort`, default `medium`), a subagent
spawn limit, and fresh one-shot context per stage. Every LLM call - including
hooked interactive Claude/Cursor sessions - lands in the usage ledger
(`midas usage`). Full rationale: `midas docs tokens`.

## Safety model

- **Auto-interrupt:** every cycle runs preflight checks (internet, disk usage
  of the workspace folder, ssh-agent with keys, installation sha256 manifest,
  agent CLI auth, Jira auth). The first fatal failure blocks the run and is
  surfaced by `midas status`.
- **Git boundary:** agents never run git write commands; Midas clones,
  branches, and commits deterministically. Nothing is ever pushed or merged —
  a human reviews the branch, merges to `review`, and attaches evidence.
- **Auto-approved agents** run confined to the task's repo working directory
  with full stream-json transcripts kept under
  `~/.local/state/midas/tasks/<KEY>/transcripts/`.
- Completion reports land in `~/.local/state/midas/completed/<KEY>.md`.

## Development

```bash
make venv     # .venv with -e .[dev]
make test     # pytest
make deb      # build the .deb
```

Bundled agent skills live in `src/midas/skills/` — the `midas-*` skills are
headless adaptations; `vendor/` holds the original team skills they wrap
(qa-validation, staged-validation-commit-message, Enonic best practices...).
