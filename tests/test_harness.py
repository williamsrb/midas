"""Bundled harness: manifest, currency, patch selection, install, rollback."""

from __future__ import annotations

import json

import pytest

from midas import harness, integrate, paths


# --------------------------------------------------------------------- manifest

def test_manifest_covers_every_kind_it_ships():
    m = harness.build_manifest()
    kinds = {i.kind for i in m.items}
    # The nine-kind taxonomy: at minimum these must be present in the bundle.
    for expected in ("skill", "rule", "hook", "agent", "kb", "quality-gate", "mcp", "cli"):
        assert expected in kinds, f"no bundled items of kind {expected!r}"
    assert all(k in harness.KINDS for k in kinds)


def test_manifest_version_is_content_addressed_and_stable():
    a = harness.build_manifest()
    b = harness.build_manifest()
    assert a.version == b.version, "same content must yield the same version"
    assert len(a.version) == 64


def test_manifest_version_changes_when_an_item_changes():
    m = harness.build_manifest()
    mutated = harness.Manifest(version="", generated_from="t", items=list(m.items))
    mutated.items[0] = harness.Item(**{**vars(m.items[0]), "sha256": "deadbeef"})
    assert harness._digest_items(mutated.items) != m.version


def test_mandatory_items_are_the_safety_and_correctness_ones():
    m = harness.build_manifest()
    mandatory = {f"{i.kind}/{i.id}" for i in m.mandatory()}
    # git-write denial is a safety invariant; the context-resolution KB entry is what
    # every skill's context budget delegates to.
    assert "hook/git-push-policy.sh" in mandatory
    assert "kb/implementation/How-to-resolve-task-context.md" in mandatory
    assert "rule/token-efficiency-chat" in mandatory
    # ... and improvements are not mandatory (R21: mandatory must stay meaningful)
    assert not any(i.kind == "agent" and i.mandatory for i in m.items)


def test_manifest_round_trips_through_toml(tmp_path):
    m = harness.build_manifest()
    dest = tmp_path / "MANIFEST.toml"
    harness.write_manifest(m, dest)
    loaded = harness.load_manifest(dest)
    assert loaded.version == m.version
    assert len(loaded.items) == len(m.items)
    assert {i.id for i in loaded.mandatory()} == {i.id for i in m.mandatory()}


def test_external_items_carry_no_payload():
    m = harness.build_manifest()
    external = [i for i in m.items if i.external]
    assert external, "rtk / offline-reference must be declared external"
    for i in external:
        assert i.bytes == 0, f"{i.id} is external but claims a payload"


# --------------------------------------------------------------------- currency

def test_never_installed_reports_every_mandatory_item_missing():
    cur = harness.currency()
    assert cur.state == "never-installed"
    assert cur.missing_mandatory
    assert cur.outdated


def test_current_when_everything_applied():
    m = harness.build_manifest()
    harness.save_applied(m.version, {f"{i.kind}/{i.id}": i.sha256 for i in m.items}, ["/tmp"])
    cur = harness.currency(m)
    assert cur.state == "current"
    assert not cur.outdated
    assert cur.label() == "current"


def test_behind_is_a_choice_but_outdated_is_not():
    m = harness.build_manifest()
    optional = next(i for i in m.items if not i.mandatory)
    applied = {f"{i.kind}/{i.id}": i.sha256 for i in m.items}
    del applied[f"{optional.kind}/{optional.id}"]
    harness.save_applied(m.version, applied, ["/tmp"])

    cur = harness.currency(m)
    assert cur.state == "behind", "missing an optional item is 'behind', never 'outdated'"
    assert not cur.outdated
    assert not harness.warning_banner(cur), "being behind must not nag"

    mandatory = next(i for i in m.items if i.mandatory)
    del applied[f"{mandatory.kind}/{mandatory.id}"]
    harness.save_applied(m.version, applied, ["/tmp"])
    cur = harness.currency(m)
    assert cur.state == "outdated"
    assert cur.outdated


def test_outdated_banner_is_loud_and_actionable():
    m = harness.build_manifest()
    applied = {f"{i.kind}/{i.id}": i.sha256 for i in m.items}
    missing = next(i for i in m.items if i.mandatory)
    del applied[f"{missing.kind}/{missing.id}"]
    harness.save_applied(m.version, applied, ["/tmp"])

    banner = harness.warning_banner(harness.currency(m))
    assert banner
    assert "OUTDATED" in banner
    assert f"{missing.kind}/{missing.id}" in banner
    assert "midas harness apply --mandatory-only" in banner, "must name the fix"
    assert "defer" in banner.lower(), "must state the cost of staying outdated"


def test_corrupt_applied_file_is_treated_as_never_installed():
    paths.harness_state_dir().mkdir(parents=True, exist_ok=True)
    paths.harness_applied_file().write_text("{not json")
    assert harness.currency().state == "never-installed"


# ----------------------------------------------------------------------- patch

def test_patch_lists_mandatory_first():
    entries = harness.available_patch()
    assert entries
    mand = [i for i, e in enumerate(entries) if e.mandatory]
    opt = [i for i, e in enumerate(entries) if not e.mandatory]
    if mand and opt:
        assert max(mand) < min(opt), "mandatory items must be offered first"


def test_patch_is_empty_once_applied():
    m = harness.build_manifest()
    harness.save_applied(m.version, {f"{i.kind}/{i.id}": i.sha256 for i in m.items}, ["/tmp"])
    assert harness.available_patch(m) == []


def test_select_honours_mandatory_only_and_kind():
    entries = harness.available_patch()
    assert all(e.mandatory for e in harness.select(entries, mandatory_only=True))
    assert all(e.kind == "rule" for e in harness.select(entries, kinds=("rule",)))


# --------------------------------------------------------------------- install

def test_plan_is_side_effect_free(tmp_path):
    root = tmp_path / "home"
    plan = integrate.plan_harness(root=root)
    assert plan
    assert not root.exists(), "planning must not touch the filesystem"


def test_install_projects_each_kind_to_both_tools(tmp_path):
    root = tmp_path / "home"
    _, installed = integrate.install_harness(root=root, snapshot=False)
    assert installed
    assert (root / ".claude" / "skills" / "midas-triage" / "SKILL.md").is_file()
    assert (root / ".cursor" / "skills" / "midas-triage" / "SKILL.md").is_file()
    assert (root / ".cursor" / "rules" / "token-efficiency-chat.mdc").is_file()
    assert (root / ".cursor" / "hooks" / "git-push-policy.sh").is_file()
    assert (root / ".claude" / "agents").is_dir()
    assert (root / ".cursor" / "kb" / "implementation" /
            "How-to-resolve-task-context.md").is_file()


def test_installed_hooks_are_executable(tmp_path):
    root = tmp_path / "home"
    integrate.install_harness(root=root, snapshot=False)
    hook = root / ".cursor" / "hooks" / "git-push-policy.sh"
    assert hook.stat().st_mode & 0o111, "a hook that is not executable never runs"


def test_second_install_is_unchanged(tmp_path):
    root = tmp_path / "home"
    integrate.install_harness(root=root, snapshot=False)
    plan = integrate.plan_harness(root=root)
    assert plan and all(w.action == "unchanged" for w in plan)


def test_only_restricts_writes_to_the_chosen_subset(tmp_path):
    root = tmp_path / "home"
    m = harness.build_manifest()
    rule = next(i for i in m.items if i.kind == "rule")
    _, installed = integrate.install_harness(
        m, root=root, only={f"rule/{rule.id}"}, snapshot=False)
    assert set(installed) == {f"rule/{rule.id}"}
    assert not (root / ".claude" / "skills").exists(), "consent means nothing else is touched"


def test_kind_filter_installs_only_that_kind(tmp_path):
    root = tmp_path / "home"
    integrate.install_harness(root=root, kinds=("rule",), snapshot=False)
    assert (root / ".cursor" / "rules").is_dir()
    assert not (root / ".claude" / "skills").exists()


def test_dry_run_writes_nothing(tmp_path):
    root = tmp_path / "home"
    plan, installed = integrate.install_harness(root=root, dry_run=True)
    assert plan and installed == {}
    assert not root.exists()


def test_install_replaces_a_symlink_rather_than_writing_through_it(tmp_path):
    """The user's own harness uses symlinks; installing must not clobber the target."""
    root = tmp_path / "home"
    target = tmp_path / "elsewhere" / "token-efficiency-chat.mdc"
    target.parent.mkdir(parents=True)
    target.write_text("ORIGINAL")
    dest = root / ".cursor" / "rules" / "token-efficiency-chat.mdc"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(target)

    integrate.install_harness(root=root, kinds=("rule",), snapshot=False)
    assert target.read_text() == "ORIGINAL", "must not write through the symlink"
    assert not dest.is_symlink()


def test_a_symlinked_target_dir_is_not_projected_twice(tmp_path):
    """~/.claude/kb -> ~/.cursor/kb means both projections are the same file.

    Planning both would double the work and report writes that do not exist.
    """
    root = tmp_path / "home"
    (root / ".cursor" / "kb").mkdir(parents=True)
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "kb").symlink_to(root / ".cursor" / "kb")

    plan = integrate.plan_harness(root=root, kinds=("kb",))
    dests = [w.dest for w in plan]
    assert len(dests) == len(set(dests))
    assert not any(".claude/kb" in str(d) for d in dests), \
        "the symlinked duplicate target must collapse into the real one"


def test_secondary_target_follows_an_existing_symlink_convention(tmp_path):
    """Where ~/.claude/skills is a directory of links into ~/.cursor/skills, keep it that way.

    Writing a second real copy would let the two tools drift apart silently - the exact
    thing the operator's symlink layout exists to prevent.
    """
    root = tmp_path / "home"
    cursor = root / ".cursor" / "skills"
    claude = root / ".claude" / "skills"
    cursor.mkdir(parents=True)
    claude.mkdir(parents=True)
    # establish the convention with a few pre-existing links
    for name in ("alpha", "beta", "gamma"):
        (cursor / name).mkdir()
        (claude / name).symlink_to(f"../../.cursor/skills/{name}")

    plan = integrate.plan_harness(root=root, kinds=("skill",))
    links = [w for w in plan if w.action == "link"]
    assert links, "expected the secondary skills target to be planned as symlinks"

    integrate.install_harness(root=root, kinds=("skill",), snapshot=False)
    linked = claude / "midas-triage"
    assert linked.is_symlink(), "secondary target must be a symlink, not a second copy"
    assert linked.resolve() == (cursor / "midas-triage").resolve()
    assert (cursor / "midas-triage" / "SKILL.md").is_file()


def test_no_symlink_convention_means_two_real_copies(tmp_path):
    """Absent a convention, both targets get real content - do not invent symlinks."""
    root = tmp_path / "home"
    plan = integrate.plan_harness(root=root, kinds=("skill",))
    assert not any(w.action == "link" for w in plan)


# ------------------------------------------------------------------------- mcp

def test_mcp_template_carries_no_secrets():
    text = (paths.harness_assets_dir() / "mcp" / "mcp.template.json").read_text()
    for marker in ("glpat-", "ATATT", "sk-"):
        assert marker not in text, f"bundled MCP template leaks a {marker} credential"


def test_mcp_resolution_fills_env_and_reports_gaps(tmp_path):
    dest = tmp_path / "mcp.json"
    _, unresolved = integrate.resolve_mcp_template(
        dest, env={"GITLAB_TOKEN": "tok-123", "BROWSER_CONTROL_MCP_SERVER": "/s.js",
                   "BROWSER_CONTROL_EXTENSION_SECRET": "sec"})
    assert unresolved == []
    data = json.loads(dest.read_text())
    assert data["mcpServers"]["gitlab-seeds"]["env"]["GITLAB_TOKEN"] == "tok-123"
    # defaults apply without being supplied
    assert data["mcpServers"]["gitlab-seeds"]["env"]["GITLAB_URL"] == "https://git.seeds.no"


def test_mcp_resolution_is_private_and_keeps_unresolved_placeholders(tmp_path):
    dest = tmp_path / "mcp.json"
    _, unresolved = integrate.resolve_mcp_template(dest, env={})
    assert "GITLAB_TOKEN" in unresolved
    assert dest.stat().st_mode & 0o777 == 0o600, "a resolved MCP config holds real tokens"
    assert "${GITLAB_TOKEN}" in dest.read_text(), \
        "an unresolved credential must fail loudly, not vanish"


# -------------------------------------------------------------------- rollback

def test_snapshot_then_rollback_restores_previous_content(tmp_path):
    home = tmp_path / "home"
    rules = home / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "token-efficiency-chat.mdc").write_text("BEFORE")

    harness.snapshot([rules], root=home)
    (rules / "token-efficiency-chat.mdc").write_text("AFTER")
    assert harness.generations()

    harness.rollback(root=home)
    assert (rules / "token-efficiency-chat.mdc").read_text() == "BEFORE"


def test_rollback_restores_into_the_root_it_was_taken_from(tmp_path):
    """A snapshot records its root, so a rollback cannot escape into the real home."""
    home = tmp_path / "sandbox"
    d = home / ".cursor" / "rules"
    d.mkdir(parents=True)
    (d / "r.mdc").write_text("BEFORE")
    harness.snapshot([d], root=home)
    (d / "r.mdc").write_text("AFTER")

    harness.rollback()          # no root given - must use the recorded one
    assert (d / "r.mdc").read_text() == "BEFORE"


def test_rollback_over_existing_symlinks_does_not_crash(tmp_path):
    """copytree(dirs_exist_ok=True) raises on an existing symlink; rollback must not.

    Regression: restoring a snapshot of ~/.claude/skills (a tree of symlinks into
    ~/.cursor/skills) failed halfway through with shutil.Error and left the harness
    partly restored.
    """
    home = tmp_path / "home"
    cursor = home / ".cursor" / "skills"
    claude = home / ".claude" / "skills"
    (cursor / "alpha").mkdir(parents=True)
    claude.mkdir(parents=True)
    (claude / "alpha").symlink_to("../../.cursor/skills/alpha")

    harness.snapshot([claude, cursor], root=home)

    # simulate an install having replaced the symlink with a real directory
    (claude / "alpha").unlink()
    (claude / "alpha").mkdir()
    (claude / "alpha" / "SKILL.md").write_text("real copy")

    harness.rollback(root=home)
    assert (claude / "alpha").is_symlink(), "the symlink convention must come back"


def test_snapshot_preserves_symlinks_as_symlinks(tmp_path):
    home = tmp_path / "home"
    cursor = home / ".cursor" / "skills"
    claude = home / ".claude" / "skills"
    (cursor / "alpha").mkdir(parents=True)
    claude.mkdir(parents=True)
    (claude / "alpha").symlink_to("../../.cursor/skills/alpha")

    snap = harness.snapshot([claude], root=home)
    assert snap is not None
    assert (snap / ".claude" / "skills" / "alpha").is_symlink(), \
        "dereferencing on snapshot would destroy the convention it protects"


def test_rollback_clears_applied_state_when_snapshot_predates_install(tmp_path):
    home = tmp_path / "home"
    d = home / ".cursor" / "rules"
    d.mkdir(parents=True)
    harness.snapshot([d], root=home)
    harness.save_applied("v1", {"rule/x": "abc"}, [str(home)])
    harness.rollback(root=home)
    assert harness.load_applied() == {}, "rolling back past an install must forget it"


def test_rollback_without_snapshots_is_an_error():
    with pytest.raises(RuntimeError, match="no harness snapshots"):
        harness.rollback()




# ------------------------------------------------------------ external probes

def test_external_verification_reports_absence_rather_than_trusting_manifest():
    m = harness.build_manifest()
    statuses = harness.verify_externals(m)
    assert statuses
    for s in statuses:
        assert isinstance(s.present, bool)
        assert s.detail, "a probe must always explain what it found"


def test_snapshot_denests_overlapping_and_aliased_targets(tmp_path):
    """Overlapping targets must collapse, or a snapshot can be written through.

    Regression: ~/.claude/kb is a symlink to ~/.cursor/kb, and .cursor/kb/validation sits
    inside .cursor/kb. Snapshotting all three produced a snapshot containing a symlink at
    .claude/kb pointing at the *live* tree; the next copy wrote through it and shutil
    aborted with "are the same file", leaving the apply half-done.
    """
    home = tmp_path / "home"
    kb = home / ".cursor" / "kb"
    (kb / "validation").mkdir(parents=True)
    (kb / "validation" / "Quality-gate-delivery-scope.md").write_text("gate")
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "kb").symlink_to(kb)

    kept = harness._denest([kb, kb / "validation", home / ".claude" / "kb",
                            home / ".claude" / "kb" / "validation"])
    assert kept == [kb], f"expected only the outermost real dir, got {kept}"

    snap = harness.snapshot([kb, kb / "validation", home / ".claude" / "kb"], root=home)
    assert snap is not None
    assert not (snap / ".claude" / "kb").exists(), \
        "an aliased target must not be snapshotted as a symlink into the live tree"
    assert (snap / ".cursor" / "kb" / "validation" /
            "Quality-gate-delivery-scope.md").read_text() == "gate"


def test_repeated_apply_all_survives_an_aliased_kb(tmp_path):
    """End-to-end guard for the same bug: two applies in a row must both succeed."""
    root = tmp_path / "home"
    kb = root / ".cursor" / "kb"
    kb.mkdir(parents=True)
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "kb").symlink_to(kb)

    integrate.install_harness(root=root)          # snapshot enabled
    integrate.install_harness(root=root)          # must not raise
    assert (kb / "validation" / "Quality-gate-delivery-scope.md").is_file()


def test_non_projectable_items_stay_out_of_the_patch_list(tmp_path):
    """`current` must be reachable.

    Regression: external items (rtk, offline-reference) and the MCP template cannot be
    placed by a projection, so they sat in "available" forever and `apply --all` left the
    machine permanently "behind (3 items)".
    """
    m = harness.build_manifest()
    assert any(not harness.projectable(i) for i in m.items), "fixture expects such items"
    keys = {e.key for e in harness.available_patch(m)}
    for i in m.items:
        if not harness.projectable(i):
            assert f"{i.kind}/{i.id}" not in keys, f"{i.id} cannot be applied - do not offer it"


def test_apply_all_reaches_current(tmp_path):
    root = tmp_path / "home"
    m = harness.build_manifest()
    entries = harness.available_patch(m)
    _, installed = integrate.install_harness(
        m, root=root, only={e.key for e in entries}, snapshot=False)
    harness.save_applied(m.version, installed, [str(root)])
    assert harness.available_patch(m) == []
    assert harness.currency(m).state == "current", "a full apply must be able to finish"


# ------------------------------------------------------------------ preflight

def test_doctor_reports_outdated_but_never_blocks_the_run(cfg):
    """An outdated harness must not be fatal - a stale client is better than none."""
    from midas import preflight
    res = preflight.check_harness(cfg)
    assert res.name == "harness"
    assert res.fatal is False, "outdated must never auto-interrupt a run"
    assert not res.ok, "a machine with nothing installed must be reported"
    assert "midas touch" in res.detail


def test_doctor_passes_once_mandatory_items_are_applied(cfg):
    from midas import preflight
    m = harness.build_manifest()
    harness.save_applied(m.version,
                         {f"{i.kind}/{i.id}": i.sha256 for i in m.projectable()}, ["/tmp"])
    res = preflight.check_harness(cfg)
    assert res.ok
    assert "current" in res.detail
