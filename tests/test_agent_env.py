import json

from midas import agent, config as config_mod
from midas.agent import _parse_stream_json_result, _subprocess_env
from midas.config import Config


def test_env_scrubs_harness_vars(monkeypatch, cfg):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://proxy")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "x")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = _subprocess_env(cfg, "claude")
    assert "ANTHROPIC_BASE_URL" not in env
    assert "CLAUDE_CODE_SESSION_ID" not in env
    assert "CLAUDECODE" not in env


def test_subscription_scrubs_api_keys(monkeypatch, cfg):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leaked")
    env = _subprocess_env(cfg, "claude")
    assert "ANTHROPIC_API_KEY" not in env


def test_api_key_injected_from_credentials(cfg):
    cfg.agents.auth = "api_key"
    config_mod.save_credential("ANTHROPIC_API_KEY", "sk-mine")
    env = _subprocess_env(cfg, "claude")
    assert env["ANTHROPIC_API_KEY"] == "sk-mine"
    # cursor gets its own key, not the anthropic one
    config_mod.save_credential("CURSOR_API_KEY", "cur-key")
    env = _subprocess_env(cfg, "cursor-agent")
    assert env.get("CURSOR_API_KEY") == "cur-key"


def test_effort_maps_to_thinking_cap(cfg):
    cfg.agents.effort = "low"
    assert _subprocess_env(cfg, "claude")["MAX_THINKING_TOKENS"] == "1024"
    cfg.agents.effort = "high"
    assert _subprocess_env(cfg, "claude")["MAX_THINKING_TOKENS"] == "31999"


def test_parse_stream_json_result_with_usage():
    lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        "garbage line",
        json.dumps({
            "type": "result", "result": "DONE", "total_cost_usd": 0.42,
            "duration_ms": 1234, "num_turns": 3, "session_id": "abc",
            "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 7},
        }),
    ]
    text, meta = _parse_stream_json_result("\n".join(lines))
    assert text == "DONE"
    assert meta["cost_usd"] == 0.42
    assert meta["usage"]["output_tokens"] == 50


def test_token_rules_mention_subagent_cap():
    assert "{max_subagents}" in agent.TOKEN_RULES
    rendered = agent.TOKEN_RULES.format(max_subagents=2)
    assert "at most 2 subagents" in rendered


def test_config_validates_new_agent_fields():
    import pytest
    c = Config()
    c.me.jira_email = "x@y.z"
    c.agents.effort = "ultra"
    with pytest.raises(config_mod.ConfigError, match="effort"):
        config_mod.validate(c)
    c.agents.effort = "medium"
    c.agents.auth = "oauth"
    with pytest.raises(config_mod.ConfigError, match="auth"):
        config_mod.validate(c)
