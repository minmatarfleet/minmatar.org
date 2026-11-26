#!/usr/bin/env python3
"""Claude Code and Cursor hooks that run CI's checks before they are needed.

Two hooks, registered in `.claude/settings.json` (and generated into
`.cursor/hooks.json` by `scripts/sync_agent_config.py`):

- pre-shell: before `git push`, run `scripts/ci_local.py` (the CI checks
  this diff needs). `gh pr create`, `gh pr ready` and `gh pr edit --body`
  run `scripts/check_pull_request.py` on the description (the push already
  ran the CI checks). A failure blocks the command and tells the agent why.
  `gh issue create` runs `scripts/check_issue.py` on its labels and body: a
  type label, and for a significant feature a design or a person's sign-off.
- pre-shell, `gh pr create`: every open issue the description closes or
  refers to must be claimed by the person (assigned, or a comment of
  theirs), and when someone else looks to be on one the person is asked to
  confirm (`scripts/issue_claims.py`).
- prompt: when a prompt names an issue, tell the person if someone else is
  already working on it, and tell the agent to claim it (assign or comment)
  before changing code.
- post-edit: after an agent edits a backend or bot Python file, report
  flake8 errors; a backend file is formatted with black first, silently.

    python3 scripts/agent_hooks.py claude pre-shell [push|pr|issue]  # JSON on stdin
    python3 scripts/agent_hooks.py cursor post-edit
    python3 scripts/agent_hooks.py claude prompt

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_claims  # noqa: E402  (scripts/ isn't a package)

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
GH_ISSUE = re.compile(SEPARATOR + r"gh\s+issue\s+create\b(.*)", re.M)
LABEL = re.compile(
    r"(?:^|\s)(?:--label|-l)(?:=|\s+)('[^']*'|\"(?:\\.|[^\"\\])*\"|\S+)"
)
CD = re.compile(SEPARATOR + r"cd\s+(\S+)", re.M)


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


def issue_labels(command: str) -> list[str]:
    """Every label a `gh issue create` passes (repeated or comma-separated)."""
    text = HEREDOC.sub("", command)
    return [
        part.strip()
        for match in LABEL.finditer(text)
        for part in _unquote(match.group(1)).split(",")
        if part.strip()
    ]


def _check_issue(repo: Path, body: str, labels: list[str]) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as out:
        out.write(body)
    try:
        return _run(
            repo,
            [
                "python3",
                "scripts/check_issue.py",
                "--body-file",
                out.name,
                "--labels",
                ",".join(labels),
            ],
        )
    finally:
        os.unlink(out.name)


def _ci(repo: Path) -> tuple[bool, str]:
    return _run(repo, ["python3", "scripts/ci_local.py"])


def _issue_problems(command: str, blank: str, cwd: Path) -> list[str]:
    """Why a `gh issue create` in the command must not run yet."""
    problems: list[str] = []
    for match in GH_ISSUE.finditer(blank):
        where = _directory(blank, match, cwd)
        repo = _repo(where)
        if not repo or not (repo / "scripts" / "check_issue.py").exists():
            continue
        if re.search(r"(^|\s)(--web|-w)\b", match.group(1)):
            continue  # the browser form applies the labels itself
        body, why = pr_body(command, where)
        if body is None and why != "no --body or --body-file":
            problems.append(
                f"Can't check the issue body: {why}. Write it to a file and "
                "pass `--body-file <file>` so the hook can run "
                "scripts/check_issue.py on it."
            )
            continue
        ok, text = _check_issue(repo, body or "", issue_labels(command))
        if not ok:
            problems.append(
                "The issue isn't ready to open (scripts/check_issue.py, "
                ".claude/rules/issues.md):\n" + text
            )
    return problems


def gate(command: str, cwd: Path, only: str | None = None) -> str | None:
    """Why the command must not run yet, or None to let it run.

    `only` ("push", "pr" or "issue") limits the gate to that kind of
    command: Claude runs one filtered hook per kind (`if` in
    .claude/settings.json), so a compound command is checked once.
    """
    if SKIP in command:
        return None
    blank = _blank(command)
    problems: list[str] = []
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

    for match in GIT_PUSH.finditer(blank) if only in (None, "push") else ():
        rest = match.group(2)
        if re.search(r"(^|\s)(--delete|-d|--tags|--dry-run|-n)(\s|$)", rest):
            continue
        if re.search(r"\s:\S", rest):  # git push origin :branch deletes
            continue
        repo = _repo(_directory(blank, match, cwd))
        if repo:
            ci(repo)

    for match in GH_PR.finditer(blank) if only in (None, "pr") else ():
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

    if only in (None, "issue"):
        problems.extend(_issue_problems(command, blank, cwd))

    if not problems:
        return None
    return "\n\n".join(problems) + (
        "\n\nThe command did not run. Fix the above and run it again."
    )


def claims_gate(command: str, cwd: Path) -> tuple[str | None, str | None]:
    """(why to block, what to ask the person) for the issues a new pull
    request refers to; (None, None) when there is nothing to say."""
    blank = _blank(command)
    block: list[str] = []
    ask: list[str] = []
    for match in GH_PR.finditer(blank):
        if match.group(1) != "create":
            continue
        where = _directory(blank, match, cwd)
        repo = _repo(where)
        slug = repo and issue_claims.repo_slug(repo)
        body, _ = pr_body(command, where)
        if not repo or not slug or not body:
            continue
        found = issue_claims.report(
            repo, issue_claims.body_issues(body, slug), slug
        )
        if found.unclaimed:
            block.append(
                "Claim the issues this pull request refers to before opening "
                "it, so nobody else starts on them "
                "(.claude/rules/issues.md):\n"
                + "\n".join(f"- {line}" for line in found.unclaimed)
            )
        ask.extend(found.warnings)
    block_text = "\n\n".join(block) or None
    ask_text = None
    if ask:
        ask_text = (
            "Someone else may already be working on an issue this pull "
            "request refers to:\n"
            + "\n".join(f"- {line}" for line in ask)
            + "\nOpen the pull request anyway?"
        )
    return block_text, ask_text


def prompt_report(prompt: str, cwd: Path) -> issue_claims.Report:
    repo = _repo(cwd)
    slug = repo and issue_claims.repo_slug(repo)
    if not repo or not slug:
        return issue_claims.Report()
    numbers = issue_claims.prompt_issues(prompt, slug)
    return issue_claims.report(repo, numbers, slug)


def prompt_context(found: issue_claims.Report) -> str | None:
    """What the agent is told about the issues a prompt names."""
    lines = []
    if found.warnings:
        lines.append(
            "Someone else may already be working on an issue in this prompt "
            "(the person has been shown this too). Tell the person and ask "
            "whether to go ahead before changing any code for it:"
        )
        lines += [f"- {line}" for line in found.warnings]
    if found.unclaimed:
        lines.append(
            "These issues aren't claimed by the person yet. If you are going "
            "to work on one (not just read or answer about it), claim it "
            "first so nobody else starts on it:"
        )
        lines += [f"- {line}" for line in found.unclaimed]
    lines += found.context
    if not lines:
        return None
    return "GitHub issues (scripts/issue_claims.py):\n" + "\n".join(lines)


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
    # Formatting is silent: Claude Code notices the file changed and asks for
    # a re-read only when the next edit needs one.
    black = _tool(repo, "black") if rel.startswith("backend/") else None
    if black:
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
    if len(argv) not in (3, 4) or argv[1] not in ("claude", "cursor"):
        print(__doc__, file=sys.stderr)
        return 1
    client, event = argv[1], argv[2]
    only = argv[3] if len(argv) == 4 else None
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    cwd = Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".")

    if event == "pre-shell":
        command = data.get("command")
        if command is None:
            command = (data.get("tool_input") or {}).get("command", "")
        claim_block, ask = (
            claims_gate(command or "", cwd.resolve())
            if only in (None, "pr")
            else (None, None)
        )
        reason = "\n\n".join(
            r
            for r in (claim_block, gate(command or "", cwd.resolve(), only))
            if r
        )
        if client == "claude":
            if reason:
                print(reason, file=sys.stderr)
                return 2
            if ask:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "ask",
                                "permissionDecisionReason": ask,
                            }
                        }
                    )
                )
            return 0
        out = {"permission": "allow"}
        if reason:
            out = {
                "permission": "deny",
                "agent_message": reason,
                "user_message": "Blocked: CI checks, the PR checklist or "
                "an unclaimed issue.",
            }
        elif ask:
            out = {
                "permission": "ask",
                "user_message": ask,
                "agent_message": ask,
            }
        print(json.dumps(out))
        return 0

    if event == "prompt":
        found = prompt_report(data.get("prompt") or "", cwd.resolve())
        warning = None
        if found.warnings:
            warning = "Someone may already be working on this:\n" + "\n".join(
                f"- {line}" for line in found.warnings
            )
        if client == "claude":
            context = prompt_context(found)
            out = {}
            if warning:
                out["systemMessage"] = warning
            if context:
                out["hookSpecificOutput"] = {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            if out:
                print(json.dumps(out))
            return 0
        out = {"continue": True}
        if warning:
            out["user_message"] = warning
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
