from midas import disk


def test_usage_and_free(tmp_path):
    (tmp_path / "blob.bin").write_bytes(b"x" * 10_000)
    usage = disk.workspace_usage_bytes(tmp_path)
    assert usage >= 10_000
    assert disk.free_bytes(tmp_path) > 0


def test_check_limits_ok(tmp_path):
    assert disk.check(tmp_path, max_workspace_gb=1, min_free_disk_gb=0.001) == []


def test_check_workspace_over_limit(tmp_path):
    (tmp_path / "blob.bin").write_bytes(b"x" * 100_000)
    problems = disk.check(tmp_path, max_workspace_gb=0.00001, min_free_disk_gb=0.001)
    assert any("limit" in p for p in problems)


def test_check_min_free_impossible(tmp_path):
    problems = disk.check(tmp_path, max_workspace_gb=1000, min_free_disk_gb=10_000_000)
    assert any("free" in p for p in problems)


def test_missing_dir_is_zero(tmp_path):
    assert disk.workspace_usage_bytes(tmp_path / "nope") == 0
