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
discovered -> fetched -> triaged -> env_detected -> cloned -> branch_ready
-> planned(planner_model) -> implemented(implementer_model)
-> validated(validator_model) -> committed -> reported -> awaiting_human
   (resting: awaiting_spec | answered   terminal: skipped_dotnet | blocked)
```

A per-task lock guarantees the same task is never processed twice
concurrently (cron cycle + a manual `midas task`, or overlapping cycles).

### Triage (before any expensive model runs)

Right after download, the cheap utility model classifies the task:

- **Question task** - the analyst is asking, not requesting code. Midas
  answers immediately (implementer model, may consult MCP tools) and posts
  the answer as a restricted Jira comment -> stage `answered`.
- **Insufficient spec** (`jira.spec_check`) - when the description is too
  poor to implement without guessing, midas posts specific questions as a
  restricted Jira comment -> stage `awaiting_spec`. When the analyst replies,
  rework detection picks the task up again.
- **Implementation task with a good spec** - continues down the pipeline.

### Rework rounds (task bounced back)

When a finished task (`awaiting_human`, `awaiting_spec`, `answered`, even
`blocked`) shows up in the poll again - status back in the pickup set and
updated since midas last saw it - midas requeues it: the previous round's
`task.md`/`plan.md` are archived as `*.roundN.md`, the task is re-downloaded,
and triage diffs the comments to classify the analyst feedback as a
**requirements change** or **complementary info**. The planner then receives
the feedback and the previous plan and plans the *delta* on the same branch.
Tasks can bounce any number of rounds.

### Jira interaction rules

- **All midas comments are restricted** to the Jira group in
  `jira.comment_group` (visibility: group). With no group configured, midas
  never posts - answers/questions are saved in the task state dir instead.
- `jira.auto_transition = true` moves the issue to `jira.in_progress_status`
  when midas starts working on it (non-fatal when the transition is missing).

### Working-time commits

With `worktime.enforce = true`, commits that would land outside the company
bracket get their git author/committer dates clamped to the most recent
in-bracket moment (a few minutes before closing time, previous working day
when needed). Configure `worktime.start`, `worktime.end`, `worktime.days`.

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
| `jira.spec_check` | triage judges spec sufficiency | `true` |
| `jira.comment_group` | Jira group that sees midas comments | `""` (never post) |
| `jira.auto_transition` | move issue to In Progress on start | `false` |
| `worktime.enforce` | clamp commit dates into working hours | `false` |
| `notify.enabled` | Slack/WhatsApp notifications (`midas docs notifications`) | `false` |

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
