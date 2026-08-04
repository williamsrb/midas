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
    _write_bundle(
        "1.0.0",
        """
        let buf = '';
        process.stdin.on('data', c => buf += c);
        process.stdin.on('end', () => {
          const req = JSON.parse(buf);
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
