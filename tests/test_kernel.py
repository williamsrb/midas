import hashlib
import textwrap

import pytest

from midas import kernel, paths


def _write_bundle(version: str, script: str) -> None:
    kernel.install(version, {kernel.BUNDLE_NAME: textwrap.dedent(script).encode()})
    kernel.activate(version)


def test_install_verifies_and_activates(tmp_path):
    _write_bundle("1.0.0", "console.log('hi')\n")
    assert kernel.installed_versions() == ["1.0.0"]
    assert kernel.active_version() == "1.0.0"
    assert kernel.verify("1.0.0") == []


def test_install_detects_tampering_after_the_fact():
    _write_bundle("1.0.0", "console.log('hi')\n")
    bundle = paths.kernel_dir() / "1.0.0" / kernel.BUNDLE_NAME
    bundle.write_text("console.log('tampered')\n")
    problems = kernel.verify("1.0.0")
    assert any("modified" in p for p in problems)


def test_install_rejects_a_signature_it_cannot_verify_yet():
    with pytest.raises(NotImplementedError):
        kernel.install("1.0.0", {kernel.BUNDLE_NAME: b"x"}, signature=b"sig")


def test_activate_refuses_an_uninstalled_version():
    with pytest.raises(kernel.KernelError):
        kernel.activate("9.9.9")


def test_run_dispatches_every_ndjson_frame_and_reports_success():
    # Reads only the first stdin *line*, matching morpheus's real kernel (apps/kernel/src/main.ts)
    # since S5a/S5b: stdin is never closed by midas immediately anymore (a client_action needs it
    # to stay open), so a fixture that waits for full-stream EOF before producing output would
    # deadlock against `kernel.run()`'s own stdin-stays-open-until-stdout-closes behavior.
    _write_bundle(
        "1.0.0",
        """
        import { createInterface } from 'node:readline';
        const rl = createInterface({ input: process.stdin, terminal: false });
        rl.once('line', (line) => {
          const req = JSON.parse(line);
          console.log(JSON.stringify({ type: 'run_started', runId: req.runId, seq: 1 }));
          console.log(JSON.stringify({ type: 'run_finished', seq: 2 }));
          process.exit(0);
        });
        """,
    )
    events = []
    outcome = kernel.run({"runId": "r1"}, events.append)
    assert outcome.state == "succeeded"
    assert outcome.exit_code == 0
    assert [e["type"] for e in events] == ["run_started", "run_finished"]
    assert events[0]["runId"] == "r1"


def test_run_client_action_round_trip():
    """The bidirectional half of spec §5.1: the fake bundle plays morpheus's kernel role - emits
    a client_action_call, blocks (via readline, same as the real kernel) for the matching
    client_action_reply on the same stdin stream, then finishes based on what it got back."""
    _write_bundle(
        "1.0.0",
        """
        import { createInterface } from 'node:readline';
        const rl = createInterface({ input: process.stdin, terminal: false });
        const lines = rl[Symbol.asyncIterator]();
        (async () => {
          const first = await lines.next();
          const req = JSON.parse(first.value);
          console.log(JSON.stringify({ type: 'run_started', runId: req.runId, seq: 1 }));
          console.log(JSON.stringify({ type: 'client_action_call', requestId: 'r1', nodeId: 'n1', action: 'git.clone', with: { url: 'x' } }));
          const reply = await lines.next();
          const parsed = JSON.parse(reply.value);
          console.log(JSON.stringify({ type: 'run_finished', seq: 2, data: { replyOk: parsed.ok, replyData: parsed.data } }));
          process.exit(parsed.ok ? 0 : 1);
        })();
        """,
    )
    events = []
    seen_calls = []

    def on_client_action(frame):
        seen_calls.append(frame)
        assert frame["action"] == "git.clone"
        assert frame["with"] == {"url": "x"}
        return {"ok": True, "data": {"path": "/workspace/repo"}}

    outcome = kernel.run({"runId": "r1"}, events.append, on_client_action=on_client_action)
    assert outcome.state == "succeeded"
    assert len(seen_calls) == 1
    # client_action_call is a transport frame, not forwarded to on_event.
    assert [e["type"] for e in events] == ["run_started", "run_finished"]
    assert events[-1]["data"]["replyOk"] is True
    assert events[-1]["data"]["replyData"] == {"path": "/workspace/repo"}


def test_run_with_no_client_action_handler_still_replies_so_the_kernel_does_not_hang():
    _write_bundle(
        "1.0.0",
        """
        import { createInterface } from 'node:readline';
        const rl = createInterface({ input: process.stdin, terminal: false });
        const lines = rl[Symbol.asyncIterator]();
        (async () => {
          await lines.next();
          console.log(JSON.stringify({ type: 'client_action_call', requestId: 'r1', nodeId: 'n1', action: 'unknown.verb', with: {} }));
          const reply = await lines.next();
          const parsed = JSON.parse(reply.value);
          console.log(JSON.stringify({ type: 'run_finished', seq: 1, data: { replyOk: parsed.ok } }));
          process.exit(0);
        })();
        """,
    )
    events = []
    outcome = kernel.run({"runId": "r1"}, events.append)  # no on_client_action given
    assert outcome.state == "succeeded"
    assert events[-1]["data"]["replyOk"] is False


def test_run_maps_every_documented_exit_code():
    for code, state in kernel.EXIT_STATE.items():
        _write_bundle(f"exit-{code}", f"process.stdin.resume(); process.exit({code});\n")
        outcome = kernel.run({}, lambda _e: None, version=f"exit-{code}")
        assert outcome.exit_code == code
        assert outcome.state == state


def test_run_kills_a_kernel_that_ignores_sigterm():
    _write_bundle(
        "hangs",
        """
        process.on('SIGTERM', () => {});
        process.stdin.resume();
        setInterval(() => {}, 1000);
        """,
    )
    outcome = kernel.run({}, lambda _e: None, version="hangs", timeout_s=0.3, kill_grace_s=0.3)
    assert outcome.state == "timeout"


def test_run_raises_when_nothing_is_installed():
    with pytest.raises(kernel.KernelError):
        kernel.run({}, lambda _e: None)


def test_run_raises_when_the_bundle_file_is_missing():
    (paths.kernel_dir() / "ghost").mkdir(parents=True)
    (paths.kernel_dir() / "ACTIVE").write_text("ghost")
    (paths.kernel_dir() / "ghost" / kernel.MANIFEST_NAME).write_text("")
    with pytest.raises(kernel.KernelError):
        kernel.run({}, lambda _e: None, version="ghost")
