import pytest

from midas import state


def test_create_and_load():
    st = state.create("RFD-1", "do a thing")
    assert state.exists("RFD-1")
    loaded = state.load("RFD-1")
    assert loaded.stage == "discovered"
    assert loaded.summary == "do a thing"


def test_advance_and_history():
    st = state.create("RFD-2")
    st.advance("fetched", "downloaded")
    st.advance("env_detected")
    loaded = state.load("RFD-2")
    assert loaded.stage == "env_detected"
    assert [h["stage"] for h in loaded.history] == ["discovered", "fetched", "env_detected"]


def test_block_is_terminal():
    st = state.create("RFD-3")
    st.block("no repo found")
    loaded = state.load("RFD-3")
    assert loaded.is_terminal
    assert loaded.stage == "blocked"
    assert loaded.error == "no repo found"


def test_unknown_stage_rejected():
    st = state.create("RFD-4")
    with pytest.raises(ValueError):
        st.advance("teleported")


def test_pending_excludes_terminal():
    state.create("RFD-5")
    st = state.create("RFD-6")
    st.advance("skipped_dotnet")
    done = state.create("RFD-7")
    done.advance("awaiting_human")
    keys = [s.key for s in state.pending()]
    assert keys == ["RFD-5"]


def test_env_roundtrip():
    st = state.create("RFD-8")
    st.save_env({"repo_url": "git@git.seeds.no:seeds/rfd.git", "enonic": True})
    assert state.load("RFD-8").env()["enonic"] is True
