from midas import usage


def test_record_and_summarize():
    usage.record("midas", agent="claude", model="opus", context="RFD-1/plan",
                 input_tokens=1000, output_tokens=200, cost_usd=0.05)
    usage.record("midas", agent="claude", model="sonnet", context="RFD-1/implement",
                 input_tokens=5000, output_tokens=2000, cost_usd=0.10)
    usage.record("claude-interactive", agent="claude", output_tokens=300)

    s = usage.summarize(days=1)
    assert s["total"]["calls"] == 3
    assert s["total"]["input_tokens"] == 6000
    assert s["total"]["output_tokens"] == 2500
    assert abs(s["total"]["cost_usd"] - 0.15) < 1e-6
    assert s["groups"]["midas/opus"]["calls"] == 1
    assert "claude-interactive/?" in s["groups"]


def test_empty_ledger():
    s = usage.summarize()
    assert s["total"]["calls"] == 0


def test_corrupt_lines_ignored(tmp_path):
    from midas import paths
    ledger = paths.usage_ledger()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("not json\n{\"broken\": true}\n")
    assert usage.load() == []
