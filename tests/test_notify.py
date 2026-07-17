from midas import config as config_mod, notify


class FakeResp:
    ok = True
    status_code = 200
    text = ""


def test_disabled_sends_nothing(cfg, monkeypatch):
    calls = []
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: calls.append(a) or FakeResp())
    assert notify.send(cfg, "blocked", "x") == []
    assert calls == []


def test_slack_delivery(cfg, monkeypatch):
    cfg.notify.enabled = True
    cfg.notify.slack_webhook = "https://hooks.slack.com/services/X"
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs.get("json")))
        return FakeResp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    assert notify.send(cfg, "blocked", "disk full") == ["slack"]
    assert calls[0][0] == cfg.notify.slack_webhook
    assert "[midas:blocked] disk full" in calls[0][1]["text"]


def test_event_filter(cfg, monkeypatch):
    cfg.notify.enabled = True
    cfg.notify.slack_webhook = "https://hooks.slack.com/services/X"
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: FakeResp())
    cfg.notify.events = ["blocked"]
    assert notify.send(cfg, "awaiting_human", "x") == []
    assert notify.send(cfg, "blocked", "x") == ["slack"]


def test_whatsapp_delivery(cfg, monkeypatch):
    cfg.notify.enabled = True
    cfg.notify.whatsapp_phone_id = "12345"
    cfg.notify.whatsapp_to = "4790000000"
    config_mod.save_credential("WHATSAPP_TOKEN", "tok")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    assert notify.send(cfg, "blocked", "x") == ["whatsapp"]
    url, kwargs = calls[0]
    assert "12345/messages" in url
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["json"]["to"] == "4790000000"


def test_whatsapp_without_token_fails_softly(cfg, monkeypatch):
    cfg.notify.enabled = True
    cfg.notify.whatsapp_phone_id = "12345"
    cfg.notify.whatsapp_to = "479"
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: FakeResp())
    assert notify.send(cfg, "blocked", "x") == []
