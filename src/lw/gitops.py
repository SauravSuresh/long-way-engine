"""Auto commit+push for lw writes. Cron runs from GitHub: unpushed = invisible."""
from __future__ import annotations

import subprocess
from pathlib import Path

TRAILER = "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"


def _git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True, check=check,
    )


def commit_and_push(
    repo_root: Path, paths: list[Path], message: str, *, push: bool = True
) -> str:
    _git(repo_root, "add", "--", *[str(p) for p in paths])
    staged = _git(repo_root, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        return ""
    _git(repo_root, "commit", "-m", f"{message}\n\n{TRAILER}")
    sha = _git(repo_root, "rev-parse", "--short", "HEAD").stdout.strip()
    if push:
        subprocess.run(
            ["gh", "auth", "switch", "-u", "SauravSuresh"],
            capture_output=True, text=True, check=False,
        )
        pull = _git(repo_root, "pull", "--rebase", "origin", "main", check=False)
        pushed = _git(repo_root, "push", "origin", "main", check=False)
        if pull.returncode != 0 or pushed.returncode != 0:
            print(f"WARNING: push failed — commit {sha} is local only. Push manually.")
    print(f"committed {sha}")
    return sha
