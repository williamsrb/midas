"""Deterministic detectors over a cloned repository tree."""

from __future__ import annotations

from pathlib import Path


def _any_glob(root: Path, patterns: list[str], depth_limit: int = 4) -> bool:
    for pattern in patterns:
        for p in root.glob(pattern):
            if len(p.relative_to(root).parts) <= depth_limit:
                return True
    return False


def is_dotnet(root: Path) -> bool:
    return _any_glob(root, ["*.sln", "**/*.sln", "**/*.csproj"])


def is_enonic(root: Path) -> bool:
    if (root / ".enonic").exists():
        return True
    if (root / "src" / "main" / "resources" / "site").is_dir():
        return True
    for gradle in list(root.glob("build.gradle")) + list(root.glob("build.gradle.kts")):
        try:
            text = gradle.read_text(errors="replace")
        except OSError:
            continue
        if "enonic" in text.lower():
            return True
    return False


def has_gitlab_ci(root: Path) -> tuple[bool, bool]:
    """Returns (has_pipeline, pipeline_mentions_review)."""
    ci = root / ".gitlab-ci.yml"
    if not ci.is_file():
        return False, False
    try:
        text = ci.read_text(errors="replace")
    except OSError:
        return True, False
    return True, "review" in text.lower()


def detect_stack(root: Path) -> str:
    if is_dotnet(root):
        return "dotnet"
    if is_enonic(root):
        return "enonic"
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        return "gradle"
    if (root / "package.json").exists():
        return "node"
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "python"
    return "unknown"


def detect_repo_traits(root: Path) -> dict:
    has_ci, ci_review = has_gitlab_ci(root)
    return {
        "stack": detect_stack(root),
        "dotnet": is_dotnet(root),
        "enonic": is_enonic(root),
        "gitlab_ci": has_ci,
        "gitlab_ci_review": ci_review,
    }
