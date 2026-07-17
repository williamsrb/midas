# Midas usage guide

Midas is an automated Jira-to-commit pipeline (Linux only, Ubuntu 24.04+).
It polls Jira for tasks assigned to you, prepares the repository, drives
headless CLI agents to plan/implement/validate, commits on a branch named
after the Jira key, and reports for human validation.

## Lifecycle

```
midas setup      # configuration wizard (detects defaults)
midas doctor     # all preflight checks, with reasons
midas enable     # install the crontab polling entry
midas disable    # remove it
```

### Agent providers

Midas supports two agent CLIs, in two auth modes each:

| Provider | Subscription mode | API-key mode |
|---|---|---|
| `claude` | reuses your `claude` login (Pro/Max). Log in: run `claude`, then `/login`, choose **Claude account with subscription**. | `ANTHROPIC_API_KEY` stored in the midas credentials file |
| `cursor-agent` | reuses your Cursor login. Log in: `cursor-agent login`. | `CURSOR_API_KEY` stored in the midas credentials file |

Pick provider and auth in `midas setup`. The non-selected provider is kept as
automatic fallback. `midas doctor` verifies the login/key and tells you how to
fix it when broken.

## Task pipeline

```
discovered -> fetched -> env_detected -> cloned -> branch_ready
-> planned(planner_model) -> implemented(implementer_model)
-> validated(validator_model) -> committed -> reported -> awaiting_human
   (terminal: skipped_dotnet | blocked)
```

- `midas run` - one full cycle (preflight, poll, advance every pending task).
- `midas task RFD-123` - force one task now; `--force` reruns a blocked task.
- `midas task FAKE-1 --from-file task.md --dry-run` - offline plumbing test
  (stops before the agent stages).
- `midas list` / `midas status` - queue, stages, disk usage, blocked state.
- `midas test RFD-123` - run the generated Playwright plan (docker) after the
  review pipeline deployed your merge.
- `midas logs [--task RFD-123] [-n 100]` - rotating logs.

## Workspace integration

- `midas touch` - installs the bundled `midas-*` skills into your
  `~/.claude/skills` and `~/.cursor/skills`, and registers the **usage hook**
  in Claude Code (`Stop` hook) and Cursor (`stop` hook) so interactive
  sessions are tracked in the same LLM ledger as midas' own runs.
- `midas greed` - scans your Claude/Cursor workspace for skills useful to the
  midas workflow (jira/git/validation/testing keywords) and, with `--import`,
  copies the chosen ones into `~/.config/midas/skills/`, which is attached to
  every agent run.
- `midas usage [--days 30]` - the LLM interaction ledger: calls, tokens, cost
  per source/model. Ledger file: `~/.local/state/midas/logs/llm-usage.jsonl`.

## Configuration

`~/.config/midas/config.toml` - all settings; `midas config` prints it.
Interesting keys:

| Key | Meaning | Default |
|---|---|---|
| `jira.pickup` | `status` (recent assigned) or `label` (opt-in) | `status` |
| `agents.primary` / `agents.auth` | provider and auth mode | `claude` / `subscription` |
| `agents.planner_model` | expensive planner | `opus` |
| `agents.implementer_model` | executor | `sonnet` |
| `agents.validator_model` | delivery reviewer | `sonnet` |
| `agents.utility_model` | cheap glue (fallbacks, detection) | `haiku` |
| `agents.effort` | thinking budget cap: low/medium/high | `medium` |
| `agents.token_saver` | terse-output rules on every prompt | `true` |
| `agents.max_subagents` | subagent spawn cap per stage | `2` |
| `limits.max_workspace_gb` | workspace folder size limit | `50` |
| `limits.min_free_disk_gb` | free disk floor | `10` |
| `cron.interval_minutes` | polling cadence | `15` |

Credentials (`~/.config/midas/credentials`, chmod 600): `JIRA_API_TOKEN`,
optionally `ANTHROPIC_API_KEY` / `CURSOR_API_KEY` for api-key auth.

## Safety model

- **Auto-interrupt preflight** on every cycle: internet, workspace disk usage,
  ssh-agent with keys, sha256 install integrity, agent login, Jira auth.
  First fatal failure blocks the run; `midas status` shows why.
- **Git boundary**: agents never run git write commands. Midas clones,
  branches and commits deterministically; it never pushes or merges - a human
  reviews the branch and merges to `review`.
- Full stream-json transcripts per stage under
  `~/.local/state/midas/tasks/<KEY>/transcripts/`.
- Completion reports: `~/.local/state/midas/completed/<KEY>.md`.
