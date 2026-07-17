import json

from midas import integrate, paths


def _mkskill(root, folder, name=None, description="does things"):
    d = root / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name or folder}\ndescription: >-\n  {description}\n---\n\n# {folder}\n"
    )
    return d


def test_parse_skill_md(tmp_path):
    d = _mkskill(tmp_path, "my-skill", description="Validates jira commit messages")
    name, desc = integrate.parse_skill_md(d / "SKILL.md")
    assert name == "my-skill"
    assert "jira commit" in desc


def test_scan_scores_and_flags_known(tmp_path, monkeypatch):
    claude_root = tmp_path / "claude-skills"
    cursor_root = tmp_path / "cursor-skills"
    _mkskill(claude_root, "jira-git-validator", description="jira git commit validation")
    _mkskill(claude_root, "cake-recipes", description="bake cakes")
    _mkskill(cursor_root, "qa-validation", description="validates the delivery")  # bundled in vendor
    monkeypatch.setattr(integrate, "CLAUDE_SKILLS", claude_root)
    monkeypatch.setattr(integrate, "CURSOR_SKILLS", cursor_root)

    found = {s.name: s for s in integrate.scan_workspace_skills()}
    assert found["jira-git-validator"].score >= 3
    assert not found["jira-git-validator"].known
    assert found["cake-recipes"].score == 0
    assert found["qa-validation"].known  # exists in bundled vendor skills


def test_import_skill(tmp_path, monkeypatch):
    root = tmp_path / "claude-skills"
    src = _mkskill(root, "jira-helper", description="jira helper")
    monkeypatch.setattr(integrate, "CLAUDE_SKILLS", root)
    monkeypatch.setattr(integrate, "CURSOR_SKILLS", tmp_path / "none")
    skill = integrate.scan_workspace_skills()[0]
    dest = integrate.import_skill(skill)
    assert dest == paths.user_skills_dir() / "jira-helper"
    assert (dest / "SKILL.md").is_file()


def test_install_skills_skips_existing(tmp_path):
    dest = tmp_path / "target"
    skills = integrate.installable_skills()
    assert skills, "bundled midas-* skills must exist"
    first = integrate.install_skills(dest, skills)
    second = integrate.install_skills(dest, skills)
    assert len(first) == len(skills)
    assert second == []


def test_install_claude_hook_merges_existing(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "existing.py stop"}]}]}
    }))
    assert integrate.install_claude_hook(settings) is True
    assert integrate.install_claude_hook(settings) is False  # idempotent
    data = json.loads(settings.read_text())
    commands = [h["command"] for e in data["hooks"]["Stop"] for h in e["hooks"]]
    assert any("existing.py" in c for c in commands)
    assert any(integrate.HOOK_NAME in c for c in commands)
    assert (paths.hooks_dir() / integrate.HOOK_NAME).is_file()


def test_install_cursor_hook_merges_existing(tmp_path):
    hooks = tmp_path / "hooks.json"
    hooks.write_text(json.dumps({
        "version": 1, "hooks": {"stop": [{"command": "./hooks/worklog-log-stop.sh"}]}
    }))
    assert integrate.install_cursor_hook(hooks) is True
    assert integrate.install_cursor_hook(hooks) is False
    data = json.loads(hooks.read_text())
    commands = [e["command"] for e in data["hooks"]["stop"]]
    assert any("worklog" in c for c in commands)
    assert any(integrate.HOOK_NAME in c for c in commands)
