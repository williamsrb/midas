from types import SimpleNamespace

import pytest

from midas import systemd


def _ok_runner(calls):
    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return runner


def _failing_runner(calls, on_args_containing: str):
    def runner(args, **kwargs):
        calls.append(args)
        if on_args_containing in args:
            return SimpleNamespace(returncode=1, stdout="", stderr="permission denied")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return runner


class TestInstall:
    def test_writes_the_unit_file_and_issues_daemon_reload_then_enable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        calls = []
        path = systemd.install(runner=_ok_runner(calls))
        assert path.is_file()
        assert "ExecStart=" in path.read_text()
        assert "agent --foreground" in path.read_text()
        assert calls == [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "--now", systemd.UNIT_NAME],
        ]

    def test_raises_systemd_error_on_a_failed_systemctl_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        calls = []
        with pytest.raises(systemd.SystemdError):
            systemd.install(runner=_failing_runner(calls, "enable"))


class TestUninstall:
    def test_removes_the_unit_and_disables_it(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        calls = []
        systemd.install(runner=_ok_runner(calls))
        assert systemd.unit_path().is_file()

        removed = systemd.uninstall(runner=_ok_runner(calls))
        assert removed is True
        assert not systemd.unit_path().is_file()

    def test_returns_false_when_nothing_is_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        assert systemd.uninstall(runner=_ok_runner([])) is False

    def test_still_removes_the_file_even_if_systemctl_disable_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        systemd.install(runner=_ok_runner([]))
        removed = systemd.uninstall(runner=_failing_runner([], "disable"))
        assert removed is True
        assert not systemd.unit_path().is_file()


class TestStatus:
    def test_not_installed_when_no_unit_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        assert systemd.status(runner=_ok_runner([])) == "not installed"

    def test_reports_is_active_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr(systemd.Path, "home", staticmethod(lambda: tmp_path))
        systemd.install(runner=_ok_runner([]))

        def runner(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout="active\n", stderr="")

        assert systemd.status(runner=runner) == "active"
