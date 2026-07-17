"""midas - command line interface."""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path

import click

from . import __version__, config as config_mod, cron, disk, logging_setup, paths, preflight, state
from .config import Config, ConfigError
from .pipeline import Pipeline


def _load_config_or_die() -> Config:
    try:
        return config_mod.load()
    except ConfigError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)


@click.group()
@click.version_option(__version__, prog_name="midas")
def main() -> None:
    """Midas - automated Jira-to-commit development pipeline.

    \b
    Lifecycle:   setup -> doctor -> enable        (then cron does the rest)
    Tasks:       run, task, list, status, test
    Workspace:   touch (install skills/hooks), greed (harvest your skills)
    Insight:     usage (LLM ledger), logs, docs, config
    """
    paths.ensure_runtime_dirs()


def _agent_login_status(provider: str) -> tuple[bool, str]:
    """(logged_in, how-to-log-in instructions) for a provider CLI."""
    if provider == "claude":
        claude_json = Path.home() / ".claude.json"
        try:
            data = json.loads(claude_json.read_text())
            email = data.get("oauthAccount", {}).get("emailAddress")
            if email:
                note = f"logged in as {email}"
                if data.get("primaryApiKey") and not data.get("hasAvailableSubscription"):
                    note += (
                        " - WARNING: Console API-key billing; headless runs fail when the "
                        "org credit is empty. Re-login choosing your Claude subscription."
                    )
                return True, note
        except (OSError, json.JSONDecodeError):
            pass
        return False, (
            "not logged in. In a normal terminal run `claude`, then `/login` and pick "
            "'Claude account with subscription' (uses your Pro/Max plan, no API key)."
        )
    # cursor-agent
    try:
        rc = subprocess.run(["cursor-agent", "status"], capture_output=True, timeout=20).returncode
    except (OSError, subprocess.TimeoutExpired):
        rc = -1
    if rc == 0:
        return True, "cursor-agent logged in"
    return False, "not logged in. Run `cursor-agent login` in a normal terminal (opens the browser)."


# ---------------------------------------------------------------- setup
@main.command()
@click.option("--non-interactive", is_flag=True, help="Accept all detected defaults.")
def setup(non_interactive: bool) -> None:
    """Create the configuration, detecting defaults from the environment."""
    logging_setup.setup()
    cfg = config_mod.detect_defaults()
    if paths.config_file().is_file():
        try:
            cfg = config_mod.load()
            click.echo(f"Existing config loaded from {paths.config_file()}")
        except ConfigError:
            click.echo("Existing config is invalid - starting from detected defaults.")

    if not non_interactive:
        cfg.me.jira_email = click.prompt("Jira email (ME)", default=cfg.me.jira_email)
        cfg.jira.base_url = click.prompt("Jira base URL", default=cfg.jira.base_url)
        cfg.jira.pickup = click.prompt(
            "Task pickup mode", default=cfg.jira.pickup,
            type=click.Choice(["status", "label"]),
        )
        if cfg.jira.pickup == "label":
            cfg.jira.label = click.prompt("Pickup label", default=cfg.jira.label)
        cfg.paths.workspace_root = click.prompt(
            "Workspace root (monitored folder)", default=cfg.paths.workspace_root
        )
        cfg.git.host = click.prompt("Git host", default=cfg.git.host)
        cfg.git.clone_url_template = click.prompt(
            "Clone URL template", default=cfg.git.clone_url_template
        )

        # --- agent provider ------------------------------------------------
        cfg.agents.primary = click.prompt(
            "Agent provider", default=cfg.agents.primary,
            type=click.Choice(["claude", "cursor-agent"]),
        )
        cfg.agents.fallback = "cursor-agent" if cfg.agents.primary == "claude" else "claude"
        auth = click.prompt(
            "Agent auth", default=cfg.agents.auth.replace("_", "-"),
            type=click.Choice(["subscription", "api-key"]),
        )
        cfg.agents.auth = auth.replace("-", "_")
        if cfg.agents.auth == "api_key":
            key_name = "ANTHROPIC_API_KEY" if cfg.agents.primary == "claude" else "CURSOR_API_KEY"
            key = click.prompt(
                f"{key_name} (stored in {paths.credentials_file()}, chmod 600)",
                default="", hide_input=True, show_default=False,
            )
            if key:
                config_mod.save_credential(key_name, key)
        else:
            logged_in, note = _agent_login_status(cfg.agents.primary)
            click.echo(f"{cfg.agents.primary}: {note}")
            if not logged_in:
                click.echo("You can finish setup now and log in afterwards; "
                           "`midas doctor` will re-check.")

        token = click.prompt(
            "Jira API token (empty = use agent+MCP fallback)",
            default="", hide_input=True, show_default=False,
        )
        if token:
            config_mod.save_credential("JIRA_API_TOKEN", token)
            click.echo(f"Token stored in {paths.credentials_file()} (chmod 600)")

        cfg.jira.comment_group = click.prompt(
            "Jira group allowed to see midas comments (empty = midas never posts)",
            default=cfg.jira.comment_group,
        )
        cfg.jira.auto_transition = click.confirm(
            f"Auto-transition tasks to '{cfg.jira.in_progress_status}' on Jira when work starts?",
            default=cfg.jira.auto_transition,
        )
        cfg.notify.enabled = click.confirm(
            "Enable notifications (Slack/WhatsApp - details in [notify] config)?",
            default=cfg.notify.enabled,
        )
        if cfg.notify.enabled and not cfg.notify.slack_webhook and not cfg.notify.whatsapp_phone_id:
            click.echo("  -> configure slack_webhook / whatsapp_* in the [notify] section; "
                       "see `midas docs notifications`")

    token = config_mod.jira_api_token()
    if token and cfg.me.jira_email:
        from .jira_rest import JiraClient, JiraError
        try:
            me = JiraClient(cfg.jira.base_url, cfg.me.jira_email, token).myself()
            cfg.me.jira_account_id = me.get("accountId", "")
            click.echo(f"Jira auth OK: {me.get('displayName', '?')} ({cfg.me.jira_account_id})")
        except JiraError as exc:
            click.echo(f"warning: Jira auth check failed: {exc}", err=True)

    imported = config_mod.import_mcp_servers()
    if imported:
        click.echo(f"MCP servers imported: {', '.join(imported)} -> {paths.mcp_file()}")

    try:
        config_mod.validate(cfg)
    except ConfigError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    path = config_mod.save(cfg)
    click.echo(f"Config written to {path}")
    click.echo("Next: run `midas doctor`, then `midas enable` to install the cron job.")


# ---------------------------------------------------------------- doctor
@main.command()
def doctor() -> None:
    """Run every preflight check and report the results."""
    logging_setup.setup()
    cfg = _load_config_or_die()
    results = preflight.run_all(cfg)
    failed = False
    for res in results:
        mark = click.style("OK  ", fg="green") if res.ok else click.style("FAIL", fg="red")
        click.echo(f"{mark} {res.name:<10} {res.detail}")
        if not res.ok and res.fatal:
            failed = True
    click.echo(f"     {'-' * 60}")
    click.echo(f"     config: {paths.config_file()}")
    click.echo(f"     state:  {paths.state_dir()}")
    sys.exit(1 if failed else 0)


# ---------------------------------------------------------------- run
@main.command()
@click.option("--cron", "from_cron", is_flag=True, help="Quiet mode for crontab runs.")
@click.option("--dry-run", is_flag=True, help="Stop each task before the agent stages.")
def run(from_cron: bool, dry_run: bool) -> None:
    """One polling cycle: preflight, poll Jira, advance every pending task."""
    logging_setup.setup(console=not from_cron)
    log = logging_setup.get("run")
    cfg = _load_config_or_die()

    lock_path = paths.locks_dir() / "run.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        click.echo("another midas run is in progress - exiting", err=True)
        sys.exit(0)

    ok, _results = preflight.guard(cfg)
    if not ok:
        blocked = preflight.blocked_status() or {}
        detail = f"preflight '{blocked.get('check')}' failed - {blocked.get('detail')}"
        click.echo(f"auto-interrupt: {detail}", err=True)
        from . import notify
        notify.send(cfg, "blocked", detail)
        sys.exit(1)

    # --- poll for new tasks
    token = config_mod.jira_api_token()
    try:
        if token:
            from .jira_rest import JiraClient
            from .poller import poll
            client = JiraClient(cfg.jira.base_url, cfg.me.jira_email, token)
            new = poll(client, cfg)
        else:
            from . import jira_agent_fallback
            new = [
                state.create(key, summary)
                for key, summary in jira_agent_fallback.poll_keys(cfg)
                if not state.exists(key)
            ]
    except Exception as exc:
        log.error("polling failed: %s", exc)
        click.echo(f"polling failed: {exc}", err=True)
        new = []

    # --- advance all pending tasks (sequential; max_concurrent_tasks=1 in v1)
    pending = state.pending()
    if not pending:
        log.info("nothing to do")
        if not from_cron:
            click.echo("no pending tasks")
        return
    for st in pending:
        log.info("processing %s (stage=%s)", st.key, st.stage)
        final = Pipeline(cfg, st, dry_run=dry_run).run()
        line = f"{st.key}: {final.stage}" + (f" - {final.error}" if final.error else "")
        log.info(line)
        if not from_cron:
            click.echo(line)


# ---------------------------------------------------------------- task
@main.command()
@click.argument("key")
@click.option("--from-file", type=click.Path(exists=True, dir_okay=False),
              help="Use a local task markdown file instead of downloading from Jira.")
@click.option("--force", is_flag=True, help="Reset a blocked/terminal task and rerun it.")
@click.option("--dry-run", is_flag=True, help="Stop before the agent stages.")
def task(key: str, from_file: str | None, force: bool, dry_run: bool) -> None:
    """Run the pipeline for a single task KEY (e.g. RFD-123)."""
    logging_setup.setup()
    cfg = _load_config_or_die()
    key = key.upper()
    if not config_mod.valid_issue_key(key):
        click.echo(f"error: '{key}' is not a valid Jira issue key", err=True)
        sys.exit(2)

    if state.exists(key):
        st = state.load(key)
        if st.is_terminal and not force:
            click.echo(
                f"{key} is in terminal stage '{st.stage}'. Use --force to rerun.", err=True
            )
            sys.exit(1)
        if force and st.is_terminal:
            st.advance(_reset_stage(st), "forced rerun")
    else:
        st = state.create(key)

    if from_file:
        st.task_md.parent.mkdir(parents=True, exist_ok=True)
        st.task_md.write_text(Path(from_file).read_text())
        if st.stage == "discovered":
            st.advance("fetched", f"task.md loaded from {from_file}")

    final = Pipeline(cfg, st, dry_run=dry_run).run()
    click.echo(f"{key}: {final.stage}" + (f" - {final.error}" if final.error else ""))
    sys.exit(0 if final.stage != "blocked" else 1)


def _reset_stage(st: state.TaskState) -> str:
    """Pick the stage to resume from on --force."""
    if st.stage == "blocked":
        # resume from the last successful stage recorded in history
        for entry in reversed(st.history[:-1]):
            if entry["stage"] in state.STAGES:
                return entry["stage"]
    return "discovered" if not st.task_md.is_file() else "fetched"


# ---------------------------------------------------------------- test
@main.command()
@click.argument("key")
def test(key: str) -> None:
    """Run the generated Playwright test plan for KEY (after the review pipeline)."""
    logging_setup.setup()
    _load_config_or_die()
    from .testrun import run_test_plan
    try:
        rc = run_test_plan(state.load(key.upper()))
    except (FileNotFoundError, RuntimeError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    sys.exit(rc)


# ---------------------------------------------------------------- status / list
@main.command()
def status() -> None:
    """Overall health: blocked state, disk usage, task queue summary."""
    logging_setup.setup(console=False)
    cfg = _load_config_or_die()
    blocked = preflight.blocked_status()
    if blocked:
        click.echo(click.style(
            f"BLOCKED since {blocked.get('at')}: [{blocked.get('check')}] {blocked.get('detail')}",
            fg="red",
        ))
    else:
        click.echo(click.style("not blocked", fg="green"))
    click.echo(disk.summary(cfg.workspace_root))
    entry = cron.installed()
    click.echo(f"cron: {entry if entry else 'not installed (run `midas enable`)'}")
    tasks = state.list_all()
    by_stage: dict[str, int] = {}
    for st in tasks:
        by_stage[st.stage] = by_stage.get(st.stage, 0) + 1
    click.echo(f"tasks: {len(tasks)} total " +
               " ".join(f"{k}={v}" for k, v in sorted(by_stage.items())))


@main.command(name="list")
def list_cmd() -> None:
    """List every known task and its stage."""
    logging_setup.setup(console=False)
    tasks = state.list_all()
    if not tasks:
        click.echo("no tasks yet")
        return
    for st in tasks:
        line = f"{st.key:<12} {st.stage:<16} {st.summary[:60]}"
        if st.error:
            line += f"  [{st.error[:80]}]"
        click.echo(line)


# ---------------------------------------------------------------- enable / disable
@main.command()
def enable() -> None:
    """Install the crontab entry that polls Jira."""
    logging_setup.setup()
    cfg = _load_config_or_die()
    click.echo(f"installed: {cron.install(cfg)}")


@main.command()
def disable() -> None:
    """Remove the midas crontab entry."""
    logging_setup.setup()
    click.echo("removed" if cron.uninstall() else "no midas cron entry found")


# ---------------------------------------------------------------- logs / config
@main.command()
@click.option("--task", "task_key", help="Show the per-task log instead.")
@click.option("-n", "lines", default=50, show_default=True, help="Lines to show.")
def logs(task_key: str | None, lines: int) -> None:
    """Show the tail of the midas log (or a task's log)."""
    if task_key:
        target = state.task_dir(task_key.upper()) / "log" / "task.log"
    else:
        target = paths.logs_dir() / "midas.log"
    if not target.is_file():
        click.echo(f"no log at {target}", err=True)
        sys.exit(1)
    out = subprocess.run(["tail", "-n", str(lines), str(target)], capture_output=True, text=True)
    click.echo(out.stdout.rstrip())


@main.command(name="config")
def config_cmd() -> None:
    """Print the configuration file path and contents."""
    path = paths.config_file()
    click.echo(f"# {path}\n")
    if path.is_file():
        click.echo(path.read_text())
    else:
        click.echo("(not created yet - run `midas setup`)")
    if paths.mcp_file().is_file():
        servers = json.loads(paths.mcp_file().read_text()).get("mcpServers", {})
        click.echo(f"# MCP servers ({paths.mcp_file()}): {', '.join(servers) or '-'}")


# ---------------------------------------------------------------- touch / greed
@main.command()
@click.option("--yes", is_flag=True, help="Install everything without asking.")
def touch(yes: bool) -> None:
    """Install midas' skills and LLM-usage hooks into your Claude/Cursor workspace."""
    logging_setup.setup()
    from . import integrate

    skills = integrate.installable_skills()
    click.echo(f"Bundled midas skills: {', '.join(s.name for s in skills)}\n")

    for label, root in (("Claude Code", integrate.CLAUDE_SKILLS),
                        ("Cursor", integrate.CURSOR_SKILLS)):
        if yes or click.confirm(f"Install midas skills into {label} ({root})?", default=True):
            installed = integrate.install_skills(root, skills)
            click.echo(f"  {label}: installed {len(installed)} skill(s)"
                       + (f" ({', '.join(installed)})" if installed else " (all already present)"))

    click.echo("\nThe usage hook records every agent turn into the midas LLM ledger\n"
               f"({paths.usage_ledger()}), like your worklog hooks do for worklogs.")
    try:
        if yes or click.confirm("Register the hook in Claude Code (~/.claude/settings.json)?",
                                default=True):
            added = integrate.install_claude_hook()
            click.echo("  claude: " + ("Stop hook registered" if added else "already registered"))
        if yes or click.confirm("Register the hook in Cursor (~/.cursor/hooks.json)?", default=True):
            added = integrate.install_cursor_hook()
            click.echo("  cursor: " + ("stop hook registered" if added else "already registered"))
    except RuntimeError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    click.echo("\nDone. Check collected data anytime with `midas usage`.")


@main.command()
@click.option("--import", "do_import", is_flag=True,
              help="Interactively import the found skills into midas.")
def greed(do_import: bool) -> None:
    """Hunt your Claude/Cursor workspace for skills midas can reuse."""
    logging_setup.setup()
    from . import integrate

    found = integrate.scan_workspace_skills()
    if not found:
        click.echo("no skills found in ~/.claude/skills or ~/.cursor/skills")
        return
    candidates = [s for s in found if not s.known]
    click.echo(f"{len(found)} skills found, {len(candidates)} not yet known to midas:\n")
    for s in found:
        tag = "known " if s.known else ("useful" if s.score else "      ")
        click.echo(f"  [{tag}] {s.name:<45} ({s.source}) {s.description[:70]}")
    if not do_import:
        if candidates:
            click.echo("\nRun `midas greed --import` to pick skills to add to midas' agent runs.")
        return
    imported = 0
    for s in candidates:
        if s.score and click.confirm(f"import '{s.name}'?", default=s.score >= 2):
            integrate.import_skill(s)
            imported += 1
    click.echo(f"\nimported {imported} skill(s) into {paths.user_skills_dir()} "
               "- agents now see them on every run.")


# ---------------------------------------------------------------- usage / docs
@main.command(name="usage")
@click.option("--days", default=7, show_default=True, help="Window in days.")
def usage_cmd(days: int) -> None:
    """LLM interaction ledger: calls, tokens and cost (midas + hooked sessions)."""
    from . import usage as usage_mod
    s = usage_mod.summarize(days)
    t = s["total"]
    if not t["calls"]:
        click.echo(f"no LLM interactions recorded in the last {days} days "
                   f"(ledger: {paths.usage_ledger()})")
        return
    click.echo(f"LLM usage, last {days} days ({t['calls']} calls):\n")
    click.echo(f"  {'source/model':<38}{'calls':>6}{'in-tok':>12}{'out-tok':>10}{'cost $':>9}")
    for key in sorted(s["groups"]):
        g = s["groups"][key]
        click.echo(f"  {key:<38}{g['calls']:>6}{g['input_tokens']:>12,}"
                   f"{g['output_tokens']:>10,}{g['cost_usd']:>9.2f}")
    click.echo(f"  {'TOTAL':<38}{t['calls']:>6}{t['input_tokens']:>12,}"
               f"{t['output_tokens']:>10,}{t['cost_usd']:>9.2f}")


@main.command()
@click.argument("topic", required=False)
def docs(topic: str | None) -> None:
    """Show midas documentation (usage | tokens)."""
    docs_dir = Path(__file__).parent / "docs"
    topics = {
        "usage": "USAGE.md",
        "tokens": "TOKEN_OPTIMIZATION.md",
        "notifications": "NOTIFICATIONS.md",
    }
    if topic in topics:
        click.echo((docs_dir / topics[topic]).read_text())
        return
    click.echo("midas documentation topics:\n")
    click.echo("  midas docs usage          - every command, workflows, configuration")
    click.echo("  midas docs tokens         - token optimization measures applied by midas")
    click.echo("  midas docs notifications  - Slack/WhatsApp setup and the future inbound channel")
    click.echo("\nQuick capability map:")
    click.echo(main.get_short_help_str(limit=200))
    for name, cmd in sorted(main.commands.items()):
        click.echo(f"  midas {name:<10} {cmd.get_short_help_str(limit=90)}")


if __name__ == "__main__":
    main()
