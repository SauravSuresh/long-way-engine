import subprocess
from pathlib import Path


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    return tmp_path


def test_commit_and_push_commits_and_returns_hash(tmp_path):
    from src.lw.gitops import commit_and_push

    repo = _init_repo(tmp_path)
    f = repo / "a.txt"
    f.write_text("hello")
    sha = commit_and_push(repo, [f], "test: hello", push=False)
    assert len(sha) >= 7
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "test: hello" in log
    assert "Co-Authored-By: Claude Fable 5" in log


def test_commit_and_push_noop_when_clean(tmp_path):
    from src.lw.gitops import commit_and_push

    repo = _init_repo(tmp_path)
    f = repo / "a.txt"
    f.write_text("x")
    commit_and_push(repo, [f], "first", push=False)
    assert commit_and_push(repo, [f], "second", push=False) == ""
