from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from midas import config as config_mod, policy, systemd
from midas.cli import main
from midas.config import Config
from midas.fleet.client import ClientIdentity


@pytest.fixture(autouse=True)
def a_saved_config(tmp_path):
    cfg = Config()
    cfg.me.jira_email = "dev@example.com"
    cfg.paths.workspace_root = str(tmp_path / "workspace")
    config_mod.save(cfg)


def _ok_runner(calls):
    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return runner


class TestEnableDisable:
    def test_enable_defaults_to_the_systemd_agent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        calls = []
        monkeypatch.setattr("subprocess.run", _ok_runner(calls))
        result = CliRunner().invoke(main, ["enable"])
        assert result.exit_code == 0, result.output
        assert "systemd user unit installed" in result.output
        assert systemd.unit_path().is_file()

    def test_enable_legacy_installs_the_crontab_entry(self, monkeypatch):
        monkeypatch.setattr("midas.cron.install", lambda cfg: "*/5 * * * * midas run --cron")
        result = CliRunner().invoke(main, ["enable", "--legacy"])
        assert result.exit_code == 0, result.output
        assert "installed:" in result.output

    def test_disable_defaults_to_removing_the_systemd_unit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr("subprocess.run", _ok_runner([]))
        systemd.install()
        result = CliRunner().invoke(main, ["disable"])
        assert result.exit_code == 0, result.output
        assert "removed" in result.output
        assert not systemd.unit_path().is_file()

    def test_disable_legacy_removes_the_crontab_entry(self, monkeypatch):
        monkeypatch.setattr("midas.cron.uninstall", lambda: True)
        result = CliRunner().invoke(main, ["disable", "--legacy"])
        assert result.exit_code == 0, result.output
        assert "removed" in result.output


class TestAgentCommand:
    def test_fails_cleanly_when_not_enrolled(self):
        result = CliRunner().invoke(main, ["agent", "--once"])
        assert result.exit_code != 0
        assert "not enrolled" in result.output

    def test_once_reports_the_cycle_result(self, monkeypatch):
        identity = ClientIdentity(server_url="http://x", client_id="cl_1", client_secret="cs_1", private_key_pem="", public_key_pem="")
        monkeypatch.setattr(ClientIdentity, "load", staticmethod(lambda: identity))
        policy.write_default("node")

        from midas.fleet import agent as agent_mod

        fake_result = agent_mod.CycleResult(heartbeat_ok=True, claimed=1, executed=[agent_mod.ExecutionResult("as_1", "succeeded")])
        monkeypatch.setattr(agent_mod, "run_once", lambda *a, **k: fake_result)

        result = CliRunner().invoke(main, ["agent", "--once"])
        assert result.exit_code == 0, result.output
        assert "claimed 1, executed 1" in result.output
        assert "as_1: succeeded" in result.output

    def test_fails_cleanly_with_no_policy_configured(self, monkeypatch):
        identity = ClientIdentity(server_url="http://x", client_id="cl_1", client_secret="cs_1", private_key_pem="", public_key_pem="")
        monkeypatch.setattr(ClientIdentity, "load", staticmethod(lambda: identity))
        result = CliRunner().invoke(main, ["agent", "--once"])
        assert result.exit_code != 0
