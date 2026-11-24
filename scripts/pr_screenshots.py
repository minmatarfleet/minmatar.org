#!/usr/bin/env python3
"""Upload screenshots for a pull request and print the markdown to paste.

`gh` can't attach images to a pull request description, so screenshots live
on the `pr-screenshots` branch (no shared history with `main`), one folder per
branch, and the description links them through raw.githubusercontent.com.
The script commits with git plumbing and a temporary index, so it never
touches the working tree, the index or the current branch.

    python3 scripts/pr_screenshots.py shots/before.png shots/after.png
    python3 scripts/pr_screenshots.py --folder 3201 fleet-390px.png

The folder defaults to the current branch name ("/" becomes "-"), so it works
before the pull request exists. A file with the same name in the folder is
replaced. Paste the printed lines under "Screenshots:" in the description
(.github/pull_request_template.md).

The repository is public: dev or seeded data only, never production pilot
data, intel or anything opsec. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BRANCH = "pr-screenshots"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_BYTES = 5 * 1024 * 1024
UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
REMOTE = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def _git(*args: str, env: dict | None = None, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()


def safe_name(name: str) -> str:
    """A file or folder name that needs no escaping in a URL or a tree."""
    cleaned = UNSAFE.sub("-", name).strip("-.")
    return cleaned or "screenshot"


def repo_slug(remote_url: str) -> str:
    match = REMOTE.search(remote_url.strip())
    if not match:
        raise SystemExit(f"origin is not a GitHub remote: {remote_url}")
    return f"{match.group(1)}/{match.group(2)}"


def markdown(slug: str, folder: str, names: list[str]) -> list[str]:
    base = f"https://raw.githubusercontent.com/{slug}/{BRANCH}/{folder}"
    return [
        f"![{Path(name).stem.replace('-', ' ')}]({base}/{quote(name)})"
        for name in names
    ]


def _check_files(paths: list[Path]) -> None:
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")
        if path.suffix.lower() not in EXTENSIONS:
            raise SystemExit(f"{path}: only {', '.join(sorted(EXTENSIONS))} images")
        if path.stat().st_size > MAX_BYTES:
            raise SystemExit(f"{path}: larger than 5 MB; crop or resize it")


def _commit(folder: str, files: dict[str, Path]) -> str:
    """Commit the files into `folder` on top of origin's branch; its sha."""
    fetched = subprocess.run(
        ["git", "fetch", "-q", "origin", f"+{BRANCH}:refs/remotes/origin/{BRANCH}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    parent = _git("rev-parse", f"origin/{BRANCH}") if fetched.returncode == 0 else ""
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        if parent:
            _git("read-tree", parent, env=env)
        for name, path in files.items():
            blob = _git("hash-object", "-w", str(path))
            _git(
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob},{folder}/{name}",
                env=env,
            )
        tree = _git("write-tree", env=env)
    args = ["commit-tree", tree, "-m", f"Screenshots for {folder}"]
    if parent:
        args[2:2] = ["-p", parent]
    return _git(*args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument(
        "--folder",
        help="folder on the pr-screenshots branch (default: the branch name)",
    )
    args = parser.parse_args(argv)

    _check_files(args.images)
    folder = safe_name(args.folder or _git("rev-parse", "--abbrev-ref", "HEAD"))
    if folder == "HEAD":
        raise SystemExit("Detached HEAD: pass --folder")
    files = {safe_name(path.name): path.resolve() for path in args.images}
    slug = repo_slug(_git("remote", "get-url", "origin"))

    for attempt in range(3):
        commit = _commit(folder, files)
        pushed = subprocess.run(
            ["git", "push", "-q", "origin", f"{commit}:refs/heads/{BRANCH}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if pushed.returncode == 0:
            break
        if attempt == 2:
            sys.stderr.write(pushed.stderr)
            return 1  # someone else kept pushing; try again later
    print("\n".join(markdown(slug, folder, list(files))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
