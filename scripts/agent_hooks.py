#!/usr/bin/env python3
"""Claude Code and Cursor hooks that run CI's checks before they are needed.

Two hooks, registered in `.claude/settings.json` (and generated into
`.cursor/hooks.json` by `scripts/sync_agent_config.py`):

- pre-shell: before `git push`, `gh pr create` or `gh pr ready`, run
  `scripts/ci_local.py` (the CI checks this diff needs), and for a pull
  request also `scripts/check_pull_request.py` on its description. A
  failure blocks the command and tells the agent why. `gh pr edit --body`
  checks only the description.
  In a Claude cloud session, the first push of a branch the session was
  given a random name for (`claude/quirky-ramanujan-mezmg0`) is blocked
  until the agent renames it to say what it does
  (`claude/esi-scope-update-task-mezmg0`).
- post-edit: after an agent edits a backend or bot Python file, report
  flake8 errors; a backend file is formatted with black first.

    python3 scripts/agent_hooks.py claude pre-shell   # JSON on stdin
    python3 scripts/agent_hooks.py cursor post-edit

A person can bypass the gate with `CI_LOCAL_SKIP=1 git push ...`. Agents
don't, unless the person asks. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SKIP = "CI_LOCAL_SKIP=1"
HOOK_TIMEOUT = 1500  # seconds; the hook itself is given 1800

HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|\)|$)", re.S
)
WRITE_HEREDOC = re.compile(
    r"(?:cat|tee)\s*>?\s*(\S+)\s*<<-?\s*(['\"]?)(\w+)\2[^\n]*\n(.*?)\n"
    r"[ \t]*\3[ \t]*(?=\n|$)",
    re.S,
)
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
SEPARATOR = r"(?:^|[;&|(\n]|\$\()\s*(?:[A-Z_]+=\S*\s+)*"
GIT_PUSH = re.compile(SEPARATOR + r"git\s+(?:-C\s+(\S+)\s+)?push\b(.*)", re.M)
GH_PR = re.compile(SEPARATOR + r"gh\s+pr\s+(create|ready|edit)\b(.*)", re.M)
CD = re.compile(SEPARATOR + r"cd\s+(\S+)", re.M)
# Claude cloud sessions name their branch claude/<adjective>-<name>-<id>.
# The cloud git proxy only accepts pushes to claude/...-<id>, so a rename
# keeps both ends and puts at least three words of summary in between.
CLOUD_BRANCH = re.compile(r"^claude/([a-z]+)-([a-z]+)-([a-z0-9]{4,})$")


# --- Reading a shell command -------------------------------------------------


def _blank(command: str) -> str:
    """The command with heredoc bodies and quoted strings emptied."""
    command = HEREDOC.sub(lambda m: "<<" + m.group(2), command)
    return QUOTED.sub("''", command)


def _unquote(word: str) -> str:
    try:
        parts = shlex.split(word)
    except ValueError:
        return word
    return parts[0] if parts else word


def _directory(blank: str, match: re.Match, cwd: Path) -> Path:
    """Where the matched command runs: the last `cd` before it, or -C."""
    where = cwd
    for cd in CD.finditer(blank, 0, match.start()):
        where = (where / os.path.expanduser(_unquote(cd.group(1)))).resolve()
    if match.re is GIT_PUSH and match.group(1):
        where = (where / _unquote(match.group(1))).resolve()
    return where


def _option(args: str, *names: str) -> str | None:
    for name in names:
        found = re.search(rf"(?:^|\s){re.escape(name)}(?:=|\s+)(\S+)", args)
        if found:
            return found.group(1)
    return None


def pr_body(command: str, cwd: Path) -> tuple[str | None, str]:
    """The description a `gh pr create/edit` passes, or (None, why not)."""
    blank = _blank(command)
    body_file = _option(blank, "--body-file", "-F")
    heredocs = [m.group(3) for m in HEREDOC.finditer(command)]
    if body_file:
        name = _unquote(_raw_word(command, "--body-file", "-F") or body_file)
        if name == "-":
            if heredocs:
                return heredocs[0], ""
            return None, "--body-file - reads stdin, which the hook can't see"
        path = (cwd / os.path.expanduser(name)).resolve()
        # `cat > body.md <<EOF ... EOF && gh pr create --body-file body.md`
        # writes the file in the same command, after this hook runs.
        for written in WRITE_HEREDOC.finditer(command):
            target = cwd / os.path.expanduser(_unquote(written.group(1)))
            if target.resolve() == path:
                return written.group(4), ""
        try:
            return path.read_text(encoding="utf-8"), ""
        except OSError:
            return None, f"can't read --body-file {name}"
    if _option(blank, "--body", "-b") is None:
        return None, "no --body or --body-file"
    if heredocs:
        return heredocs[0], ""
    literal = _raw_word(command, "--body", "-b")
    if literal and "$(" not in literal and "`" not in literal:
        if not (literal.startswith('"') and "$" in literal):
            return _unquote(literal), ""
    return None, "the --body text is built by the shell"


def _raw_word(command: str, *names: str) -> str | None:
    """The (possibly quoted) word after an option in the original command."""
    for name in names:
        found = re.search(
            rf"(?:^|\s){re.escape(name)}(?:=|\s+)"
            r"('[^']*'|\"(?:\\.|[^\"\\])*\"|\S+)",
            command,
        )
        if found:
            return found.group(1)
    return None


# --- The gate ----------------------------------------------------------------


def _repo(where: Path) -> Path | None:
    try:
        top = subprocess.run(
            ["git", "-C", str(where), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    repo = Path(top)
    return repo if (repo / "scripts" / "ci_local.py").exists() else None


def _run(repo: Path, args: list[str]) -> tuple[bool, str]:
    try:
        done = subprocess.run(
            args,
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=HOOK_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(args[:2])} timed out"
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def _check_body(repo: Path, body: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as out:
        out.write(body)
    try:
        ok, text = _run(
            repo,
            [
                "python3",
                "scripts/check_pull_request.py",
                "--body-file",
                out.name,
            ],
        )
    finally:
        os.unlink(out.name)
    errors = [
        line.replace("::error::", "- ")
        for line in text.splitlines()
        if line.startswith("::error")
    ]
    return ok, "\n".join(errors) or text


def _ci(repo: Path) -> tuple[bool, str]:
    return _run(repo, ["python3", "scripts/ci_local.py"])


def _cloud_session() -> bool:
    return os.environ.get("CLAUDE_CODE_REMOTE", "").lower() == "true"


def branch_name_problem(repo: Path) -> str | None:
    """Why a cloud session's random branch name should change before push.

    Only a branch that isn't on the remote yet: renaming a pushed branch
    would orphan its pull request.
    """
    ok, branch = _run(repo, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch.strip()
    match = CLOUD_BRANCH.match(branch) if ok else None
    if not match:
        return None
    pushed, _ = _run(
        repo,
        [
            "git",
            "rev-parse",
            "--verify",
            "-q",
            f"refs/remotes/origin/{branch}",
        ],
    )
    tracked, _ = _run(
        repo,
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
    )
    if pushed or tracked:
        return None
    suffix = match.group(3)
    return (
        f"The branch `{branch}` has the session's random name. Rename it to "
        "say what the change does (three to six lowercase words, kebab "
        f"case), keeping `claude/` and the session id `-{suffix}` so the "
        "cloud git proxy accepts the push, then push again:\n\n"
        f"    git branch -m claude/<what-it-does>-{suffix}\n"
        "    git push -u origin HEAD\n\n"
        f"For example `claude/esi-scope-update-task-{suffix}`."
    )


def _cloud_branch_gate(blank: str, cwd: Path) -> str | None:
    if not _cloud_session():
        return None
    for match in GIT_PUSH.finditer(blank):
        if re.search(r"(^|\s)(--delete|-d|--tags)(\s|$)", match.group(2)):
            continue
        repo = _repo(_directory(blank, match, cwd))
        problem = repo and branch_name_problem(repo)
        if problem:
            return problem
    return None


def gate(command: str, cwd: Path) -> str | None:
    """Why the command must not run yet, or None to let it run."""
    if SKIP in command:
        return None
    blank = _blank(command)
    problems: list[str] = []

    problem = _cloud_branch_gate(blank, cwd)
    if problem:
        # Before CI: the checks would only run again after the rename.
        return problem
    ran_ci: set[Path] = set()

    def ci(repo: Path) -> None:
        if repo in ran_ci:
            return
        ran_ci.add(repo)
        ok, text = _ci(repo)
        if not ok:
            problems.append(
                "CI checks failed (scripts/ci_local.py). Fix these first:\n"
                + text
            )

    for match in GIT_PUSH.finditer(blank):
        rest = match.group(2)
        if re.search(r"(^|\s)(--delete|-d|--tags|--dry-run|-n)(\s|$)", rest):
            continue
        if re.search(r"\s:\S", rest):  # git push origin :branch deletes
            continue
        repo = _repo(_directory(blank, match, cwd))
        if repo:
            ci(repo)

    for match in GH_PR.finditer(blank):
        verb, rest = match.group(1), match.group(2)
        where = _directory(blank, match, cwd)
        repo = _repo(where)
        if not repo:
            continue
        if (
            verb == "edit"
            and _option(rest, "--body", "-b", "--body-file", "-F") is None
        ):
            continue
        if verb == "ready" and re.search(r"(^|\s)--undo\b", rest):
            continue
        if verb == "create":
            draft = re.search(r"(^|\s)(--draft|-d)\b", rest)
        else:
            # CI checks a draft's description only when it is marked ready.
            draft = verb == "edit" and _is_draft(repo, rest)
        if verb == "ready":
            body, why = _remote_body(repo, rest)
        else:
            body, why = pr_body(command, where)
        if body is None and not draft:
            problems.append(
                f"Can't check the pull request description: {why}. Write it "
                "to a file and pass `--body-file <file>` so the hook can run "
                "scripts/check_pull_request.py on it."
            )
        elif body is not None and not draft:
            ok, text = _check_body(repo, body)
            if not ok:
                problems.append(
                    "The description fails the pull request checklist "
                    "(scripts/check_pull_request.py, "
                    ".github/pull_request_template.md):\n" + text
                )
        if verb in ("create", "ready"):
            ci(repo)

    if not problems:
        return None
    return "\n\n".join(problems) + (
        "\n\nThe command did not run. Fix the above and run it again."
    )


def _pr_target(rest: str) -> list[str]:
    try:
        words = shlex.split(rest or "")
    except ValueError:
        return []
    return [w for w in words if not w.startswith("-")][:1]


def _is_draft(repo: Path, rest: str) -> bool:
    done = subprocess.run(
        ["gh", "pr", "view", *_pr_target(rest), "--json", "isDraft"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    try:
        return bool(json.loads(done.stdout)["isDraft"])
    except (ValueError, KeyError):
        return False


def _remote_body(repo: Path, rest: str) -> tuple[str | None, str]:
    try:
        done = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                *_pr_target(rest),
                "--json",
                "body",
                "--jq",
                ".body",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, "gh pr view could not read the current description"
    return done.stdout, ""


# --- Formatting an edited file ------------------------------------------------


def _tool(repo: Path, name: str) -> str | None:
    """A lint tool from the backend venv, else from PATH."""
    cache = repo / "backend" / ".test-db" / ".venv-bin"
    try:
        bin_dir = Path(cache.read_text().strip())
    except OSError:
        bin_dir = None
        found = (
            subprocess.run(
                ["pipenv", "--venv"],
                cwd=repo / "backend",
                capture_output=True,
                text=True,
                env={**os.environ, "PIPENV_VERBOSITY": "-1"},
            )
            if shutil.which("pipenv")
            else None
        )
        if found and found.returncode == 0:
            bin_dir = Path(found.stdout.strip()) / "bin"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(str(bin_dir))
    if bin_dir and (bin_dir / name).exists():
        return str(bin_dir / name)
    return shutil.which(name)


def post_edit(path_text: str) -> tuple[str | None, bool]:
    """(message for the agent, whether it must act on it)."""
    path = Path(path_text).resolve()
    repo = _repo(path.parent)
    if not repo or path.suffix != ".py" or not path.exists():
        return None, False
    rel = path.relative_to(repo).as_posix()
    if not rel.startswith(("backend/", "bot/")):
        return None, False
    if rel.startswith("backend/scripts/") or "/migrations/" in rel:
        return None, False
    project = repo / rel.split("/", 1)[0]
    notes, act = [], False

    # Only backend/ is black-formatted; bot/ is checked by flake8 alone.
    black = _tool(repo, "black") if rel.startswith("backend/") else None
    if black:
        before = path.read_bytes()
        subprocess.run(
            [
                black,
                "-q",
                "--config",
                str(repo / "backend/pyproject.toml"),
                str(path),
            ],
            capture_output=True,
        )
        if path.read_bytes() != before:
            notes.append(
                f"black reformatted {rel}; read it before editing it again."
            )

    flake8 = _tool(repo, "flake8")
    if flake8:
        done = subprocess.run(
            [flake8, str(path)], cwd=project, capture_output=True, text=True
        )
        if done.returncode != 0 and done.stdout.strip():
            prefix = str(path) + ":"
            errors = done.stdout.strip().replace(prefix, rel + ":")
            notes.append("flake8 (CI fails on these):\n" + errors)
            act = True
    return ("\n".join(notes) or None), act


def _edited_path(data: dict) -> str | None:
    tool_input = data.get("tool_input") or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            tool_input = {}
    for key in ("file_path", "path", "target_file", "filePath"):
        if tool_input.get(key):
            return tool_input[key]
    return data.get("file_path")


# --- Clients -----------------------------------------------------------------


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("claude", "cursor"):
        print(__doc__, file=sys.stderr)
        return 1
    client, event = argv[1], argv[2]
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    cwd = Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".")

    if event == "pre-shell":
        command = data.get("command")
        if command is None:
            command = (data.get("tool_input") or {}).get("command", "")
        reason = gate(command or "", cwd.resolve())
        if client == "claude":
            if reason:
                print(reason, file=sys.stderr)
                return 2
            return 0
        out = {"permission": "allow"}
        if reason:
            out = {
                "permission": "deny",
                "agent_message": reason,
                "user_message": "Blocked: CI checks or the PR checklist fail.",
            }
        print(json.dumps(out))
        return 0

    if event == "post-edit":
        path = _edited_path(data)
        message, act = post_edit(path) if path else (None, False)
        if not message:
            return 0
        if client == "claude":
            if act:
                print(json.dumps({"decision": "block", "reason": message}))
            else:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PostToolUse",
                                "additionalContext": message,
                            }
                        }
                    )
                )
            return 0
        print(json.dumps({"additional_context": message}))
        return 0

    print(f"unknown event {event}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
