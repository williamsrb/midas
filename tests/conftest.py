import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Point every midas path at a throwaway directory."""
    monkeypatch.setenv("MIDAS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("MIDAS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("MIDAS_JIRA_TOKEN", raising=False)
    yield tmp_path


@pytest.fixture
def cfg(tmp_path):
    from midas.config import Config
    c = Config()
    c.me.jira_email = "dev@example.com"
    c.paths.workspace_root = str(tmp_path / "workspace")
    return c
