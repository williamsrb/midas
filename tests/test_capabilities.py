from midas import policy
from midas.config import Config
from midas.fleet import capabilities


def cfg(tmp_path) -> Config:
    c = Config()
    c.paths.workspace_root = str(tmp_path)
    return c


class TestBuild:
    def test_reports_the_documented_shape(self, tmp_path):
        payload = capabilities.build(cfg(tmp_path))
        assert set(payload.keys()) >= {
            "kernelVersion", "actions", "subscriptions", "tools",
            "limits", "labels", "timezone", "harnessVersion", "policySummary",
        }
        assert payload["actions"] == policy.KNOWN_ACTIONS
        assert set(payload["subscriptions"].keys()) == {"claude", "cursor", "shell"}
        assert payload["subscriptions"]["shell"] == {"present": True}

    def test_no_kernel_installed_reports_null_not_an_error(self, tmp_path):
        payload = capabilities.build(cfg(tmp_path))
        assert payload["kernelVersion"] is None

    def test_no_policy_reports_null_not_an_error(self, tmp_path):
        payload = capabilities.build(cfg(tmp_path))
        assert payload["policySummary"] is None

    def test_reports_the_written_policy_summary(self, tmp_path):
        policy.write_default("node", workspace_root=str(tmp_path))
        payload = capabilities.build(cfg(tmp_path))
        assert payload["policySummary"] == {
            "shell": False,
            "permissionCeiling": "edits",
            "repoAllowlist": [],
            "maxUsdPerRun": 5.0,
        }

    def test_passes_through_labels(self, tmp_path):
        payload = capabilities.build(cfg(tmp_path), labels=["linux", "review-env"])
        assert payload["labels"] == ["linux", "review-env"]

    def test_limits_reflect_the_configured_workspace_root(self, tmp_path):
        (tmp_path / "file.bin").write_bytes(b"x" * 1024)
        payload = capabilities.build(cfg(tmp_path))
        assert payload["limits"]["freeDiskGb"] >= 0
        assert payload["limits"]["workspaceGb"] >= 0
        assert payload["limits"]["maxConcurrentRuns"] == 1
