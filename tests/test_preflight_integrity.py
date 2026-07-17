import hashlib

from midas import preflight
from midas.config import Config


def _manifest_for(pkg_dir, files):
    lines = []
    for rel in files:
        digest = hashlib.sha256((pkg_dir / rel).read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{rel}")  # sha256sum's `./` prefix form
    return "\n".join(lines) + "\n"


def test_integrity_ok(tmp_path, monkeypatch):
    pkg = tmp_path / "pkg"
    (pkg / "detect").mkdir(parents=True)
    (pkg / "cli.py").write_text("print('hi')")
    (pkg / "detect" / "text.py").write_text("x = 1")
    manifest = pkg / "MANIFEST.sha256"
    manifest.write_text(_manifest_for(pkg, ["cli.py", "detect/text.py"]))
    monkeypatch.setattr(preflight.paths, "manifest_file", lambda: manifest)

    res = preflight.check_install_integrity(Config())
    assert res.ok, res.detail


def test_integrity_detects_tampering(tmp_path, monkeypatch):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "cli.py").write_text("print('hi')")
    manifest = pkg / "MANIFEST.sha256"
    manifest.write_text(_manifest_for(pkg, ["cli.py"]))
    (pkg / "cli.py").write_text("print('tampered')")
    monkeypatch.setattr(preflight.paths, "manifest_file", lambda: manifest)

    res = preflight.check_install_integrity(Config())
    assert not res.ok
    assert "modified cli.py" in res.detail


def test_integrity_detects_missing_file(tmp_path, monkeypatch):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "cli.py").write_text("print('hi')")
    manifest = pkg / "MANIFEST.sha256"
    manifest.write_text(_manifest_for(pkg, ["cli.py"]))
    (pkg / "cli.py").unlink()
    monkeypatch.setattr(preflight.paths, "manifest_file", lambda: manifest)

    res = preflight.check_install_integrity(Config())
    assert not res.ok
    assert "missing cli.py" in res.detail


def test_integrity_skipped_without_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight.paths, "manifest_file", lambda: tmp_path / "nope")
    res = preflight.check_install_integrity(Config())
    assert res.ok and not res.fatal
