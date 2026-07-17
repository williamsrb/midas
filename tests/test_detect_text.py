from midas.detect import (
    detect_repo_url,
    detect_review_url,
    project_from_url,
    project_key_from_issue,
)


def test_https_url_normalized_to_ssh():
    text = "Source: https://git.seeds.no/seeds/rfd"
    assert detect_repo_url(text) == "git@git.seeds.no:seeds/rfd.git"


def test_ssh_url_kept():
    text = "clone with git@git.seeds.no:seeds/rfd.git please"
    assert detect_repo_url(text) == "git@git.seeds.no:seeds/rfd.git"


def test_web_ui_suffixes_stripped():
    for suffix in ("/-/merge_requests/14", "/-/tree/review", "/blob/main/README.md"):
        text = f"see https://git.seeds.no/seeds/booking-app{suffix}"
        assert detect_repo_url(text) == "git@git.seeds.no:seeds/booking-app.git", suffix


def test_wrong_host_ignored():
    assert detect_repo_url("https://github.com/foo/bar") == ""
    assert detect_repo_url("https://git.other.io/seeds/rfd") == ""


def test_no_repo():
    assert detect_repo_url("just a plain task about buttons") == ""


def test_review_url():
    text = "deployed to https://review.as.k8s.seeds.no/tours after the pipeline."
    assert detect_review_url(text) == "https://review.as.k8s.seeds.no/tours"


def test_review_url_absent():
    assert detect_review_url("nothing here") == ""


def test_project_from_url():
    assert project_from_url("git@git.seeds.no:seeds/rfd.git") == "rfd"
    assert project_from_url("git@git.seeds.no:seeds/sub/booking-app.git") == "booking-app"


def test_project_key_from_issue():
    assert project_key_from_issue("RFD-123") == "rfd"
