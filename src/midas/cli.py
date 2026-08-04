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


def _warn_if_outdated(quiet: bool = False) -> None:
    """Print the outdated banner before anything else.

    A client missing a mandatory harness item is deprioritised for delegated work, so this
    must be impossible to miss. It lives in the group callback rather than in each command
    so a new command cannot forget it. Under --cron it goes to the log instead of stdout,
    where nobody would read it.
    """
    if quiet:
        return
    try:
        from . import harness
        banner = harness.warning_banner(harness.currency())
    except Exception:                      # never let a warning break a command
        return
    if banner:
        if "--cron" in sys.argv:
            logging_setup.get("harness").warning(banner.replace("\n", " | "))
        else:
            click.echo(click.style(banner, fg="yellow", bold=True), err=True)


@click.group()
@click.version_option(__version__, prog_name="midas")
@click.option("--no-warn", is_flag=True, help="Suppress the outdated-harness banner.")
def main(no_warn: bool) -> None:
    """Midas - automated Jira-to-commit development pipeline.

    \b
    Lifecycle:   setup -> doctor -> enable        (then cron does the rest)
    Tasks:       run, task, list, status, test
    Harness:     touch (install the harness), harness (status/list/apply/rollback),
                 greed (harvest reuse candidates)
    Insight:     usage (LLM ledger), logs, docs, config
    """
    paths.ensure_runtime_dirs()
    _warn_if_outdated(quiet=no_warn)


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


# ---------------------------------------------------------------- touch / harness / greed
_KIND_LABEL = {
    "skill": "skills", "rule": "rules", "hook": "hooks", "agent": "agents",
    "command": "commands", "kb": "knowledge base", "quality-gate": "quality gates",
    "mcp": "MCP servers", "cli": "CLI tools",
}


@main.command()
@click.option("--yes", is_flag=True, help="Install everything without asking.")
@click.option("--dry-run", is_flag=True, help="Show what would be written and stop.")
@click.option("--kind", "kinds", multiple=True,
              type=click.Choice(sorted(_KIND_LABEL)),
              help="Limit to these item kinds (repeatable).")
@click.option("--mcp/--no-mcp", default=None,
              help="Also write ~/.config/midas/mcp.json from the bundled template.")
@click.option("--root", type=click.Path(file_okay=False), default=None,
              help="Projection root (default: your home directory).")
def touch(yes: bool, dry_run: bool, kinds: tuple[str, ...], mcp: bool | None,
          root: str | None) -> None:
    """Install the bundled AI harness into this machine's Claude/Cursor setup.

    Installs every kind of harness item - skills, rules, hooks, agents, commands,
    knowledge base, quality gates - not just skills. Run it on a fresh machine to bring
    it up to the same standard as the machine the harness was curated on.
    """
    logging_setup.setup()
    from . import harness, integrate

    manifest = harness.load_manifest()
    proj_root = Path(root).expanduser() if root else Path.home()

    counts: dict[str, int] = {}
    for item in manifest.items:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    click.echo(f"Bundled harness {manifest.version[:12]} - {len(manifest.items)} items "
               f"({len(manifest.mandatory())} mandatory):")
    for kind in sorted(counts):
        click.echo(f"  {_KIND_LABEL.get(kind, kind):<16} {counts[kind]}")
    click.echo()

    plan = integrate.plan_harness(manifest, root=proj_root, kinds=kinds)
    writes = [w for w in plan if w.action != "unchanged"]
    if not writes:
        click.echo("Everything is already up to date on this machine.")
    else:
        by_action: dict[str, int] = {}
        for w in writes:
            by_action[w.action] = by_action.get(w.action, 0) + 1
        click.echo("  ".join(f"{n} to {a}" for a, n in sorted(by_action.items())))
        for w in writes[:15]:
            click.echo(f"    {w.action:<8} {w.dest}")
        if len(writes) > 15:
            click.echo(f"    ... and {len(writes) - 15} more")

    if dry_run:
        click.echo("\n(dry run - nothing written)")
        return

    if writes and (yes or click.confirm(f"\nInstall into {proj_root}?", default=True)):
        _, installed = integrate.install_harness(manifest, root=proj_root, kinds=kinds)
        prev = harness.load_applied().get("items", {})
        prev.update(installed)
        harness.save_applied(manifest.version if not kinds else "", prev, [str(proj_root)])
        click.echo(f"  installed {len(installed)} item(s)")

    # MCP template: only ever written with resolved secrets, mode 0600
    if mcp or (mcp is None and (yes or click.confirm(
            "Write the MCP server config from the bundled template?", default=False))):
        dest, unresolved = integrate.resolve_mcp_template()
        click.echo(f"  mcp: {dest} (0600)")
        if unresolved:
            click.echo(click.style(
                f"  mcp: {len(unresolved)} unresolved placeholder(s): {', '.join(unresolved)}\n"
                "       set them in the environment or "
                f"{paths.credentials_file()} and re-run - the server will fail loudly until then",
                fg="yellow"))

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

    ext = harness.verify_externals(manifest)
    if ext:
        click.echo("\nExternal tools (not bundled - verified by probe):")
        for e in ext:
            mark = "ok     " if e.present else ("MISSING" if e.mandatory else "absent ")
            click.echo(f"  [{mark}] {e.item_id:<20} {e.detail}")

    click.echo("\nDone. `midas harness status` shows what this machine has.")


@main.group(name="harness")
def harness_cmd() -> None:
    """Inspect, patch and roll back this machine's AI harness."""


@harness_cmd.command(name="status")
def harness_status() -> None:
    """Show the installed harness version and whether it is current."""
    from . import harness

    manifest = harness.load_manifest()
    cur = harness.currency(manifest)
    applied_items = len(harness.load_applied().get("items", {}))
    click.echo(f"available : {manifest.version[:12]}  ({len(manifest.items)} items, "
               f"{len(manifest.mandatory())} mandatory)")
    if cur.applied_version:
        click.echo(f"applied   : {cur.applied_version[:12]}  ({applied_items} items)")
    elif applied_items:
        click.echo(f"applied   : partial      ({applied_items}/{len(manifest.items)} items)")
    else:
        click.echo("applied   : -")
    click.echo(f"state     : {cur.label()}")
    if cur.missing_mandatory:
        click.echo("\nmissing mandatory:")
        for m in cur.missing_mandatory:
            click.echo(f"  - {m}")
    if cur.behind and not cur.missing_mandatory:
        click.echo(f"\n{len(cur.behind)} optional item(s) behind - `midas harness list`")
    ext = harness.verify_externals(manifest)
    if ext:
        click.echo("\nexternal tools:")
        for e in ext:
            click.echo(f"  [{'ok' if e.present else 'absent'}] {e.item_id:<20} {e.detail}")


@harness_cmd.command(name="list")
@click.option("--mandatory-only", is_flag=True, help="Only mandatory items.")
def harness_list(mandatory_only: bool) -> None:
    """List harness items available to apply on this machine."""
    from . import harness

    entries = harness.select(harness.available_patch(), mandatory_only=mandatory_only)
    if not entries:
        click.echo("nothing to apply - this machine is current")
        return
    click.echo(f"{len(entries)} item(s) available "
               f"({sum(1 for e in entries if e.mandatory)} mandatory):\n")
    for e in entries:
        flag = "!" if e.mandatory else " "
        ext = " (external)" if e.external else ""
        click.echo(f" {flag} {e.change:<8} {e.kind:<13} {e.item_id}{ext}")
    click.echo("\nApply with: midas harness apply [--mandatory-only | --all]")


@harness_cmd.command(name="apply")
@click.option("--all", "apply_all", is_flag=True, help="Apply every available item.")
@click.option("--mandatory-only", is_flag=True, help="Apply only mandatory items.")
@click.option("--kind", "kinds", multiple=True, type=click.Choice(sorted(_KIND_LABEL)),
              help="Limit to these kinds (repeatable).")
@click.option("--dry-run", is_flag=True, help="Show the plan and stop.")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@click.option("--root", type=click.Path(file_okay=False), default=None,
              help="Projection root (default: your home directory).")
def harness_apply(apply_all: bool, mandatory_only: bool, kinds: tuple[str, ...],
                  dry_run: bool, yes: bool, root: str | None) -> None:
    """Apply a chosen subset of available harness items.

    Nothing is applied unless you ask: pick --all, --mandatory-only, or --kind.
    """
    logging_setup.setup()
    from . import harness, integrate

    proj_root = Path(root).expanduser() if root else Path.home()

    if not (apply_all or mandatory_only or kinds):
        click.echo("choose what to apply: --all, --mandatory-only, or --kind <kind>", err=True)
        sys.exit(2)

    manifest = harness.load_manifest()
    entries = harness.select(harness.available_patch(manifest),
                             mandatory_only=mandatory_only, kinds=kinds)
    if not entries:
        click.echo("nothing to apply")
        return
    only = {e.key for e in entries}
    click.echo(f"{len(entries)} item(s) selected "
               f"({sum(1 for e in entries if e.mandatory)} mandatory)")
    for e in entries[:20]:
        click.echo(f"  {e.change:<8} {e.kind:<13} {e.item_id}")
    if len(entries) > 20:
        click.echo(f"  ... and {len(entries) - 20} more")

    if dry_run:
        integrate.install_harness(manifest, root=proj_root, only=only, dry_run=True)
        click.echo("\n(dry run - nothing written)")
        return
    if not (yes or click.confirm(f"\nApply into {proj_root}?", default=True)):
        return

    cur_all = harness.currency(manifest)
    _, installed = integrate.install_harness(manifest, root=proj_root, only=only)
    prev = harness.load_applied().get("items", {})
    prev.update(installed)
    harness.save_applied(harness.load_applied().get("version", ""), prev, [str(proj_root)])
    # Claim the full version only once nothing at all is left to apply.
    if not harness.available_patch(manifest):
        harness.save_applied(manifest.version, prev, [str(proj_root)])
    click.echo(f"applied {len(installed)} item(s)")
    after = harness.currency(manifest)
    click.echo(f"state: {after.label()}")
    if not after.outdated and cur_all.outdated:
        click.echo("no longer outdated - Morpheus will stop deferring work from this client")


@harness_cmd.command(name="verify")
def harness_verify() -> None:
    """Re-hash the live projections and probe every external tool."""
    from . import harness, integrate

    manifest = harness.load_manifest()
    plan = integrate.plan_harness(manifest)
    drifted = [w for w in plan if w.action == "update"]
    missing = [w for w in plan if w.action == "create"]
    click.echo(f"{len(plan)} projection(s) checked: "
               f"{len(plan) - len(drifted) - len(missing)} match, "
               f"{len(drifted)} differ, {len(missing)} absent")
    for w in (drifted + missing)[:20]:
        click.echo(f"  {w.action:<8} {w.dest}")
    click.echo()
    for e in harness.verify_externals(manifest):
        mark = "ok    " if e.present else ("MISSING" if e.mandatory else "absent")
        click.echo(f"  [{mark}] {e.kind}/{e.item_id:<20} {e.detail}")


@harness_cmd.command(name="rollback")
@click.option("--to", "generation", default=None, help="Generation stamp (default: newest).")
@click.option("--yes", is_flag=True, help="Do not ask for confirmation.")
@click.option("--root", type=click.Path(file_okay=False), default=None,
              help="Projection root (default: the root recorded in the snapshot).")
def harness_rollback(generation: str | None, yes: bool, root: str | None) -> None:
    """Restore a retained harness generation."""
    logging_setup.setup()
    from . import harness

    gens = harness.generations()
    if not gens:
        click.echo("no snapshots retained - nothing to roll back to", err=True)
        sys.exit(1)
    target = generation or gens[0]
    click.echo(f"retained: {', '.join(gens)}")
    if not (yes or click.confirm(f"restore {target} over the live harness?", default=False)):
        return
    try:
        restored = harness.rollback(target, Path(root).expanduser() if root else None)
        click.echo(f"rolled back to {restored}")
    except (RuntimeError, OSError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)


@harness_cmd.command(name="reindex")
def harness_reindex() -> None:
    """Rebuild the bundled MANIFEST.toml from the packaged harness tree (maintainer task)."""
    from . import harness

    manifest = harness.build_manifest()
    dest = harness.write_manifest(manifest)
    click.echo(f"{dest}\nversion {manifest.version}\n{len(manifest.items)} items, "
               f"{len(manifest.mandatory())} mandatory")


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
    """Show midas documentation (usage | tokens | harness | notifications)."""
    docs_dir = Path(__file__).parent / "docs"
    topics = {
        "usage": "USAGE.md",
        "tokens": "TOKEN_OPTIMIZATION.md",
        "harness": "HARNESS.md",
        "notifications": "NOTIFICATIONS.md",
    }
    if topic in topics:
        click.echo((docs_dir / topics[topic]).read_text())
        return
    click.echo("midas documentation topics:\n")
    click.echo("  midas docs usage          - every command, workflows, configuration")
    click.echo("  midas docs tokens         - token optimization measures applied by midas")
    click.echo("  midas docs harness        - the bundled AI harness, versions, patches, rollback")
    click.echo("  midas docs notifications  - Slack/WhatsApp setup and the future inbound channel")
    click.echo("\nQuick capability map:")
    click.echo(main.get_short_help_str(limit=200))
    for name, cmd in sorted(main.commands.items()):
        click.echo(f"  midas {name:<10} {cmd.get_short_help_str(limit=90)}")


if __name__ == "__main__":
    main()
