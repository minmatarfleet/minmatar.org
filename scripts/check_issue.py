#!/usr/bin/env python3
"""Check a GitHub issue's labels and, for a feature, its design.

Every issue carries at least one type label from `.github/labels.json`
(feature, bug, user-feedback, security, tech-debt), so a person can see at a
glance what kind of work it is. A significant feature (a new page, tab or
flow, or a reworked layout) needs a design linked under "### Design", or a
person's sign-off that it ships without one under "### Design sign-off" and
"### Signed off by". The issue forms in `.github/ISSUE_TEMPLATE/` write
those headings; an agent writing the body by hand uses the same ones
(`.claude/rules/issues.md`).

    python3 scripts/check_issue.py --labels feature --body-file body.md
    python3 scripts/check_issue.py --github   # in .github/workflows/issues.yml

On the command line it prints what is missing and exits 1. With --github it
reads ISSUE_BODY and ISSUE_LABELS (JSON list) and writes the labels to add
and remove (needs-triage, needs-design) to GITHUB_OUTPUT; the workflow
applies them, so a person sees what an issue still needs. Standard library
only. `backend/app/tests/test_issue_check.py` tests it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS_FILE = ROOT / ".github" / "labels.json"
NEEDS_DESIGN = "needs-design"
NEEDS_TRIAGE = "needs-triage"
NO_RESPONSE = "_No response_"

COMMENT = re.compile(r"<!--.*?-->", re.S)
HEADING = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.M)
URL = re.compile(r"https?://\S+")
TICKED = re.compile(r"^\s*[-*]\s+\[[xX]\]", re.M)
HANDLE = re.compile(r"@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)")
AGENT_HANDLES = re.compile(r"(\[bot\]|^claude|^cursor|^copilot|^codex)", re.I)


def type_labels() -> list[str]:
    data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    return [label["name"] for label in data if label.get("group") == "type"]


def sections(body: str) -> dict[str, str]:
    """{lower-cased `##`/`###` heading: its text}, comments removed."""
    text = COMMENT.sub("", (body or "").replace("\r\n", "\n"))
    found = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip()
        found[match.group(1).strip().lower()] = "" if value == NO_RESPONSE else value
    return found


def is_significant(found: dict[str, str]) -> bool:
    """Unless the issue says it is small or invisible, assume it is not."""
    size = found.get("size", "").lower()
    return not size.startswith(("small", "nothing visible"))


def design_problem(found: dict[str, str]) -> str | None:
    """Why a feature still needs a design, or None when it doesn't."""
    if not is_significant(found):
        return None
    if URL.search(found.get("design", "")):
        return None
    signed_off = TICKED.search(found.get("design sign-off", ""))
    handle = HANDLE.search(found.get("signed off by", ""))
    if signed_off and handle and not AGENT_HANDLES.search(handle.group(1)):
        return None
    if signed_off and handle:
        return (
            f"@{handle.group(1)} is an agent or bot; a person signs off a "
            "feature without a design."
        )
    return (
        'A significant feature needs a design linked under "### Design" (a '
        "Claude design artifact, wireframe canvas, Figma file or mock-up), "
        'or a person\'s sign-off: a ticked box under "### Design sign-off" '
        'and their @handle and reason under "### Signed off by". Agents: ask '
        "the person which they want; never sign off for them."
    )


def check(body: str, labels: list[str]) -> tuple[list[str], set[str]]:
    """(problems, status labels the issue should carry)."""
    problems: list[str] = []
    status: set[str] = set()
    types = type_labels()
    if not any(label in types for label in labels):
        problems.append(
            f"Give the issue a type label: {', '.join(types)} (more than one "
            "is fine, e.g. user-feedback and bug)."
        )
        status.add(NEEDS_TRIAGE)
    if "feature" in labels:
        why = design_problem(sections(body))
        if why:
            problems.append(why)
            status.add(NEEDS_DESIGN)
    return problems, status


def _labels(values: list[str]) -> list[str]:
    return [
        part.strip() for value in values for part in value.split(",") if part.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--labels", action="append", default=[])
    parser.add_argument("--body-file")
    parser.add_argument(
        "--github",
        action="store_true",
        help="read ISSUE_BODY/ISSUE_LABELS, write label changes to GITHUB_OUTPUT",
    )
    args = parser.parse_args(argv)

    if args.github:
        body = os.environ.get("ISSUE_BODY", "")
        labels = json.loads(os.environ.get("ISSUE_LABELS") or "[]")
    else:
        body = (
            Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
        )
        labels = _labels(args.labels)

    problems, status = check(body, labels)

    if args.github:
        managed = {NEEDS_DESIGN, NEEDS_TRIAGE}
        add = sorted(status - set(labels))
        remove = sorted((managed - status) & set(labels))
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"add={','.join(add)}\n")
            out.write(f"remove={','.join(remove)}\n")
            out.write(f"design_added={'true' if NEEDS_DESIGN in add else 'false'}\n")
        for problem in problems:
            print(f"::notice::{problem}")
        return 0

    for problem in problems:
        print(f"- {problem}")
    if problems:
        return 1
    print("Issue check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
