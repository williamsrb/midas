"""Kernel bundle management and invocation (spec `midas_changes_plan.md` §1.1).

Midas does not execute playbooks itself — it spawns the Node kernel bundle Morpheus
publishes (`apps/kernel` in the morpheus repo, bundled to `midas-kernel.mjs`) and speaks
its `KernelRequest`/`RunEvent` NDJSON protocol over stdin/stdout. That keeps one engine
implementation, run identically in-process by Morpheus or as a subprocess here — this
module owns the client half: install/verify a bundle, and run it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import paths

MANIFEST_NAME = "MANIFEST.sha256"
BUNDLE_NAME = "midas-kernel.mjs"

# Exit codes the kernel promises (apps/kernel/src/main.ts's EXIT table).
EXIT_SUCCEEDED = 0
EXIT_FAILED = 1
EXIT_GATE = 2
EXIT_ABORTED = 3
EXIT_INVALID_REQUEST = 4
EXIT_INTERNAL = 5

EXIT_STATE = {
    EXIT_SUCCEEDED: "succeeded",
    EXIT_FAILED: "failed",
    EXIT_GATE: "gate",
    EXIT_ABORTED: "aborted",
    EXIT_INVALID_REQUEST: "invalid_request",
    EXIT_INTERNAL: "internal",
}


class KernelError(Exception):
    pass


@dataclass
class KernelOutcome:
    exit_code: int
    state: str
    stderr: str = ""


def installed_versions() -> list[str]:
    root = paths.kernel_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / BUNDLE_NAME).is_file())


def active_version() -> str | None:
    marker = paths.kernel_dir() / "ACTIVE"
    if not marker.is_file():
        return None
    version = marker.read_text().strip()
    return version if version in installed_versions() else None


def _verify_manifest(version_dir: Path) -> list[str]:
    """Return a list of problems against the version's own manifest; empty means clean.

    Same sha256sum-line format and comparison `preflight.check_install_integrity` already
    uses for the package's own install manifest — one hashing convention, not two.
    """
    manifest = version_dir / MANIFEST_NAME
    if not manifest.is_file():
        return [f"missing {MANIFEST_NAME}"]
    bad: list[str] = []
    for line in manifest.read_text().splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        expected, rel = parts[0], parts[1].strip().lstrip("./")
        target = version_dir / rel
        if not target.is_file():
            bad.append(f"missing {rel}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            bad.append(f"modified {rel}")
    return bad


def verify(version: str) -> list[str]:
    """Re-hash an installed version's tree against its manifest. Empty list means clean."""
    version_dir = paths.kernel_dir() / version
    if not version_dir.is_dir():
        return [f"kernel {version} is not installed"]
    return _verify_manifest(version_dir)


def install(
    version: str,
    files: dict[str, bytes],
    *,
    signature: bytes | None = None,
    pubkey: bytes | None = None,
) -> None:
    """Write a kernel bundle's files and verify each against a manifest computed on write.

    `signature`/`pubkey` are accepted in the signature but not yet checked: there is no
    fleet client in this phase to hold a trusted pubkey to check them against (that lands
    with `fleet/client.py` in Phase 2). A bundle claiming to be signed is refused rather
    than silently installed unverified.
    """
    if signature is not None:
        raise NotImplementedError(
            "kernel signature verification needs a fleet-enrolled pubkey (Phase 2); "
            "install an unsigned bundle for offline/standalone use in the meantime"
        )
    version_dir = paths.kernel_dir() / version
    version_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines = []
    for rel, data in files.items():
        target = version_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  ./{rel}")
    (version_dir / MANIFEST_NAME).write_text("\n".join(manifest_lines) + "\n")

    problems = _verify_manifest(version_dir)
    if problems:
        raise KernelError(f"kernel {version} failed self-verification after install: {', '.join(problems)}")


def activate(version: str) -> None:
    if version not in installed_versions():
        raise KernelError(f"kernel {version} is not installed")
    paths.kernel_dir().mkdir(parents=True, exist_ok=True)
    (paths.kernel_dir() / "ACTIVE").write_text(version)


def run(
    request: dict,
    on_event: Callable[[dict], None],
    *,
    version: str | None = None,
    timeout_s: float | None = None,
    kill_grace_s: float = 5.0,
) -> KernelOutcome:
    """Spawn the kernel bundle, feed `request` as JSON on stdin, dispatch each NDJSON
    frame from stdout to `on_event`, and return the terminal outcome.

    Timeout is enforced the same shape `agent.py` already uses for agent subprocesses:
    SIGTERM, then SIGKILL after a grace period if the process ignores it.
    """
    version = version or active_version()
    if not version:
        raise KernelError("no kernel installed - run `midas kernel install` first")
    bundle = paths.kernel_dir() / version / BUNDLE_NAME
    if not bundle.is_file():
        raise KernelError(f"kernel {version} bundle missing: {bundle}")

    proc = subprocess.Popen(
        ["node", str(bundle)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(request))
    proc.stdin.close()

    timed_out = threading.Event()
    timer: threading.Timer | None = None
    if timeout_s is not None:
        def _on_timeout() -> None:
            timed_out.set()
            proc.terminate()
            grace = threading.Timer(kill_grace_s, proc.kill)
            grace.daemon = True
            grace.start()

        timer = threading.Timer(timeout_s, _on_timeout)
        timer.daemon = True
        timer.start()

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            on_event(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn line from a full buffer; events.ndjson on disk is authoritative
    proc.wait()
    if timer is not None:
        timer.cancel()

    stderr = proc.stderr.read() if proc.stderr else ""
    if timed_out.is_set():
        return KernelOutcome(EXIT_INTERNAL, "timeout", stderr)
    return KernelOutcome(proc.returncode, EXIT_STATE.get(proc.returncode, "unknown"), stderr)
