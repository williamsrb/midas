import pytest

from midas import config as config_mod, paths
from midas.config import Config, ConfigError


def test_save_load_roundtrip(cfg):
    config_mod.save(cfg)
    loaded = config_mod.load()
    assert loaded.me.jira_email == "dev@example.com"
    assert loaded.jira.pickup == "status"
    assert loaded.limits.max_workspace_gb == 50.0


def test_load_missing_file_raises():
    with pytest.raises(ConfigError, match="midas setup"):
        config_mod.load()


def test_unknown_key_rejected(cfg):
    config_mod.save(cfg)
    path = paths.config_file()
    path.write_text(path.read_text() + "\n[jira]\nbogus_key = 1\n")
    with pytest.raises(ConfigError):
        config_mod.load()


def test_validate_pickup_mode(cfg):
    cfg.jira.pickup = "everything"
    with pytest.raises(ConfigError, match="pickup"):
        config_mod.validate(cfg)


def test_validate_requires_email():
    c = Config()
    c.me.jira_email = ""
    with pytest.raises(ConfigError, match="jira_email"):
        config_mod.validate(c)


def test_validate_clone_template(cfg):
    cfg.git.clone_url_template = "git@git.seeds.no:seeds/fixed.git"
    with pytest.raises(ConfigError, match="clone_url_template"):
        config_mod.validate(cfg)


def test_credentials_roundtrip():
    config_mod.save_credential("JIRA_API_TOKEN", "abc123")
    assert config_mod.jira_api_token() == "abc123"
    assert (paths.credentials_file().stat().st_mode & 0o777) == 0o600


def test_env_token_wins(monkeypatch):
    config_mod.save_credential("JIRA_API_TOKEN", "from-file")
    monkeypatch.setenv("MIDAS_JIRA_TOKEN", "from-env")
    assert config_mod.jira_api_token() == "from-env"


def test_valid_issue_key():
    assert config_mod.valid_issue_key("RFD-123")
    assert config_mod.valid_issue_key("AS2-9")
    assert not config_mod.valid_issue_key("rfd-123")
    assert not config_mod.valid_issue_key("RFD123")
    assert not config_mod.valid_issue_key("RFD-123x")
