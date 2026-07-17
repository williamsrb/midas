from midas.detect import detect_repo_traits
from midas.detect.repo import detect_stack, is_dotnet, is_enonic


def make(root, *files, content=""):
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def test_dotnet_detected(tmp_path):
    make(tmp_path, "src/App/App.csproj")
    assert is_dotnet(tmp_path)
    assert detect_repo_traits(tmp_path)["stack"] == "dotnet"


def test_enonic_by_gradle(tmp_path):
    make(tmp_path, "build.gradle", content="plugins { id 'com.enonic.xp.app' }")
    assert is_enonic(tmp_path)
    assert detect_stack(tmp_path) == "enonic"


def test_enonic_by_site_dir(tmp_path):
    make(tmp_path, "src/main/resources/site/site.xml")
    assert is_enonic(tmp_path)


def test_plain_gradle_not_enonic(tmp_path):
    make(tmp_path, "build.gradle", content="plugins { id 'java' }")
    assert not is_enonic(tmp_path)
    assert detect_stack(tmp_path) == "gradle"


def test_node_and_python(tmp_path):
    make(tmp_path, "package.json", content="{}")
    assert detect_stack(tmp_path) == "node"


def test_gitlab_ci_review(tmp_path):
    make(tmp_path, ".gitlab-ci.yml", content="deploy-review:\n  only: [review]\n")
    traits = detect_repo_traits(tmp_path)
    assert traits["gitlab_ci"] and traits["gitlab_ci_review"]


def test_empty_repo(tmp_path):
    traits = detect_repo_traits(tmp_path)
    assert traits["stack"] == "unknown"
    assert not traits["dotnet"] and not traits["enonic"] and not traits["gitlab_ci"]
