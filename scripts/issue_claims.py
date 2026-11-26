#!/usr/bin/env python3
"""Who is working on a GitHub issue, and has this person claimed it?

Used by `scripts/agent_hooks.py` so two people (or their agents) don't build
the same thing:

- When a prompt names an issue (`#123`, `issue 123`, an issues URL), the hook
  looks it up. If someone else is on it (assigned, an open pull request of
  theirs references it, or they said so in a recent comment) the person is
  told before any work starts. Otherwise the agent is told to claim it before
  changing code: assign themselves when their GitHub access allows it
  (triage or more), else comment that they are picking it up.
- Before `gh pr create`, every open issue the description closes or refers
  to must be claimed by the person opening it (assigned, or a comment of
  theirs), and someone else's claim asks the person to confirm.

It calls `gh`. When `gh` is missing, signed out or offline, nothing is
reported and nothing is blocked. Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

GH_TIMEOUT = 15  # seconds per gh call
MAX_ISSUES = 5
CLAIM_DAYS = 30
ASSIGN_ACCESS = {"admin", "maintain", "write", "triage"}

# github.com URLs, and SSH host aliases from ~/.ssh/config ("git@github-work:owner/repo.git").
REMOTE = re.compile(
    r"(?:github\.com[:/]|^git@[\w.-]+:)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$"
)
# A fork's issues live on the repository it was forked from.
REMOTE_NAMES = ("upstream", "origin")
# "#123", "issue 123", "issues/123" (a URL to this repo is checked by slug).
PROMPT_REF = re.compile(
    r"(?:(?<![\w/&])#(\d{2,})\b|\bissue\s+#?(\d{2,})\b|"
    r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+))",
    re.I,
)
ISSUE_REF = r"(?:#(\d+)|https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+))"
BODY_REF = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?|references|"
    r"related(?:\s+to)?|part\s+of|see|follow-up\s+to)\s*:?\s+" + ISSUE_REF,
    re.I,
)
CLAIM = re.compile(
    r"\b(?:i'?m|i am|we'?re|we are)\s+(?:on (?:it|this)|working on|"
    r"picking (?:this|it) up|taking (?:this|it))|\bi'?ll take\b|"
    r"\bpicking (?:this|it) up\b|\bworking on (?:this|it)\b|\bclaim(?:ing)?\b",
    re.I,
)

QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        number title state url
        assignees(first: 10) { nodes { login } }
        comments(last: 20) { nodes { author { login } createdAt body } }
        timelineItems(last: 50,
            itemTypes: [CROSS_REFERENCED_EVENT, CONNECTED_EVENT]) {
          nodes {
            ... on CrossReferencedEvent { source { ...pr } }
            ... on ConnectedEvent { subject { ...pr } }
          }
        }
      }
    }
  }
}
fragment pr on PullRequest { number state url author { login } }
"""


@dataclass
class Issue:
    number: int
    title: str
    open: bool
    url: str
    assignees: list[str] = field(default_factory=list)
    # (login, created_at, body), oldest first
    comments: list[tuple[str, datetime, str]] = field(default_factory=list)
    # (number, url, author) of open pull requests that reference it
    open_prs: list[tuple[int, str, str]] = field(default_factory=list)


def _gh(repo: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["gh", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def repo_slug(repo: Path) -> str | None:
    """owner/name of the repository whose issues the hooks check: the
    ``upstream`` remote in a fork, otherwise ``origin``."""
    for name in REMOTE_NAMES:
        try:
            url = subprocess.run(
                ["git", "remote", "get-url", name],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        match = REMOTE.search(url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def prompt_issues(text: str, slug: str) -> list[int]:
    """Issue numbers a prompt names, in order, at most MAX_ISSUES."""
    found: list[int] = []
    for match in PROMPT_REF.finditer(text or ""):
        if match.group(3) and match.group(3).lower() != slug.lower():
            continue
        number = int(match.group(1) or match.group(2) or match.group(4))
        if number not in found:
            found.append(number)
    return found[:MAX_ISSUES]


def body_issues(text: str, slug: str) -> list[int]:
    """Issues a pull request description closes or refers to."""
    found: list[int] = []
    for match in BODY_REF.finditer(text or ""):
        if match.group(2) and match.group(2).lower() != slug.lower():
            continue
        number = int(match.group(1) or match.group(3))
        if number not in found:
            found.append(number)
    return found[:MAX_ISSUES]


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def parse_issue(data: dict) -> Issue | None:
    node = (((data or {}).get("data") or {}).get("repository") or {}).get(
        "issueOrPullRequest"
    )
    if not node or node.get("__typename") != "Issue":
        return None  # a pull request number, or no such issue
    issue = Issue(
        number=node["number"],
        title=node["title"],
        open=node["state"] == "OPEN",
        url=node["url"],
        assignees=[a["login"] for a in node["assignees"]["nodes"]],
    )
    for comment in node["comments"]["nodes"]:
        login = (comment.get("author") or {}).get("login") or "ghost"
        issue.comments.append((login, _time(comment["createdAt"]), comment["body"]))
    seen = set()
    for event in node["timelineItems"]["nodes"]:
        pr = (event or {}).get("source") or (event or {}).get("subject")
        if not pr or "number" not in pr or pr["number"] in seen:
            continue
        seen.add(pr["number"])
        if pr["state"] == "OPEN":
            author = (pr.get("author") or {}).get("login") or "ghost"
            issue.open_prs.append((pr["number"], pr["url"], author))
    return issue


def fetch_issue(repo: Path, slug: str, number: int) -> Issue | None:
    owner, name = slug.split("/", 1)
    out = _gh(
        repo,
        "api",
        "graphql",
        "-f",
        f"query={QUERY}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
        "-F",
        f"number={number}",
    )
    try:
        return parse_issue(json.loads(out)) if out else None
    except (ValueError, KeyError, TypeError):
        return None


def current_login(repo: Path) -> str | None:
    out = _gh(repo, "api", "user", "--jq", ".login")
    return out.strip() if out and out.strip() else None


def can_assign(repo: Path, slug: str, login: str) -> bool:
    out = _gh(
        repo,
        "api",
        f"repos/{slug}/collaborators/{login}/permission",
        "--jq",
        ".permission",
    )
    return bool(out) and out.strip() in ASSIGN_ACCESS


def others_on_it(issue: Issue, me: str, now: datetime | None = None) -> list[str]:
    """Why someone else looks to be working on the issue, one line each."""
    now = now or datetime.now(timezone.utc)
    mine = me.lower()
    reasons = []
    others = [a for a in issue.assignees if a.lower() != mine]
    if others:
        reasons.append("assigned to " + ", ".join(f"@{login}" for login in others))
    for number, url, author in issue.open_prs:
        if author.lower() != mine:
            reasons.append(f"@{author} has open pull request #{number} ({url})")
    claimers = []
    for login, created, body in issue.comments:
        if (
            login.lower() != mine
            and login not in claimers
            and now - created <= timedelta(days=CLAIM_DAYS)
            and CLAIM.search(body)
        ):
            claimers.append(login)
    for login in claimers:
        if login not in others:
            reasons.append(f"@{login} said in a recent comment they are on it")
    return reasons


def claimed_by(issue: Issue, me: str) -> bool:
    mine = me.lower()
    return any(a.lower() == mine for a in issue.assignees) or any(
        login.lower() == mine for login, _, _ in issue.comments
    )


def claim_command(issue: Issue, assign: bool) -> str:
    if assign:
        return f"gh issue edit {issue.number} --add-assignee @me"
    return f"gh issue comment {issue.number} --body " '"I\'m picking this up."'


@dataclass
class Report:
    """What the person and the agent are told about the issues."""

    warnings: list[str] = field(default_factory=list)  # for the person
    context: list[str] = field(default_factory=list)  # for the agent
    unclaimed: list[str] = field(default_factory=list)  # claim commands


def report(repo: Path, numbers: list[int], slug: str | None = None) -> Report:
    result = Report()
    slug = slug or repo_slug(repo)
    if not numbers or not slug:
        return result
    me = current_login(repo)
    if not me:
        return result
    assign = None
    for number in numbers:
        issue = fetch_issue(repo, slug, number)
        if not issue:
            continue
        if not issue.open:
            result.context.append(f"Issue #{number} is closed.")
            continue
        busy = others_on_it(issue, me)
        if busy:
            result.warnings.append(f"#{number} {issue.title}: " + "; ".join(busy) + ".")
        if claimed_by(issue, me):
            continue  # nothing for the agent to do
        if assign is None:
            assign = can_assign(repo, slug, me)
        command = claim_command(issue, assign)
        result.unclaimed.append(f"#{number}: `{command}`")
    return result
