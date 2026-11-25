#!/usr/bin/env python3
"""Check a pull request's description against .github/pull_request_template.md.

The template asks for the quality controls every pull request goes through.
This script reads the description and the files the pull request changes and
fails when a control that applies is missing:

- Issue: every pull request says which issue it closes ("Closes #123") or
  refers to ("Refs #123"), or ticks "No issue for this change" and says why.
- Frontend review: a change under `frontend/app/` needs "Ran the frontend
  review on the final diff" ticked and the frontend-review skill's result.
- Backend review: a change under `backend/` or `bot/` needs "Ran the backend
  review on the final diff" ticked and the backend-review skill's result.
- Rust component library: adding to `frontend/app/rust/library.ts`, changing
  a component listed there or a composition, or changing a design token
  (`frontend/app/src/styles/properties/`) needs the box ticked, the
  components named, a human justification and who gave it.
- Documentation: one of the two boxes ticked. "Updated the docs" needs a doc
  in the diff; "No documented behaviour changed" needs a reason when a doc
  names a file the pull request changes.

`.github/workflows/pull-request.yml` runs it on every pull request (drafts
pass until they are marked ready). Run it locally before opening one:

    python3 scripts/check_pull_request.py --body-file body.md [--base origin/main]

Standard library only. `backend/app/tests/test_pull_request_check.py` tests it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FRONTEND_PREFIXES = ("frontend/app/",)
BACKEND_PREFIXES = ("backend/", "bot/")
RUST_LIBRARY = "frontend/app/rust/library.ts"
COMPONENTS = "frontend/app/src/components/"
COMPOSITIONS = "frontend/app/src/components/compositions/"
TOKENS = "frontend/app/src/styles/properties/"
# Where a doc may name a repo path relative to, besides the repo root.
PATH_BASES = (
    "backend/",
    "frontend/app/src/",
    "frontend/app/",
    "desktop/",
    "mobile/",
    "bot/",
)
# Handles that are agents or bots, not the person justifying a Rust change.
AGENT_HANDLES = re.compile(r"(\[bot\]|^claude|^cursor|^copilot|^codex)", re.I)

COMMENT = re.compile(r"<!--.*?-->", re.S)
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)
LIBRARY_ENTRY = re.compile(r"'((?:[\w-]+/)+[\w-]+)'")
HANDLE = re.compile(r"@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)")
PLACEHOLDER = re.compile(r"<short sha>|<one line per")
# "Closes #12", "fixes owner/repo#12", "Refs https://github.com/o/r/issues/12".
ISSUE_REF = r"(?:[\w.-]+/[\w.-]+)?#\d+|https://github\.com/[\w.-]+/[\w.-]+/issues/\d+"
CLOSES = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:" + ISSUE_REF + ")",
    re.I,
)
REFERS = re.compile(
    r"\b(?:refs?|references|related(?:\s+to)?|part\s+of|see|follow-up\s+to)"
    r"\s*:?\s+(?:" + ISSUE_REF + ")",
    re.I,
)
BARE_ISSUE = re.compile(ISSUE_REF)
MIN_REASON = 10

# Labels in the order they appear, per section, so a field's text runs up to
# the next label.
LABELS = {
    "issue": ["Issue"],
    "frontend review": ["Result"],
    "backend review": ["Result"],
    "rust component library": [
        "Components / tokens",
        "Human justification",
        "Justified by",
    ],
    "documentation": ["Docs updated, or why none needed"],
}
MIN_JUSTIFICATION = 40


# --- Description parsing ---------------------------------------------------


def sections(body: str) -> dict[str, str]:
    """{lower-cased `##` heading: its text}, with HTML comments removed."""
    text = COMMENT.sub("", body.replace("\r\n", "\n"))
    found = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found[match.group(1).strip().lower()] = text[match.end() : end]
    return found


def ticked(section: str, phrase: str) -> bool:
    pattern = re.compile(r"^\s*[-*]\s+\[[xX]\]\s+" + re.escape(phrase), re.M | re.I)
    return bool(pattern.search(section))


def field(section: str, label: str, labels: list[str]) -> str:
    """Text after `label:`, up to the next label or checkbox; stripped."""
    start = re.search(r"^\s*" + re.escape(label) + r"\s*:", section, re.M | re.I)
    if not start:
        return ""
    rest = section[start.end() :]
    stops = [
        re.search(r"^\s*" + re.escape(other) + r"\s*:", rest, re.M | re.I)
        for other in labels
        if other != label
    ]
    stops.append(re.search(r"^\s*[-*]\s+\[[ xX]\]", rest, re.M))
    end = min((stop.start() for stop in stops if stop), default=len(rest))
    text = rest[:end]
    # Blockquotes and code fences are fine wrappers; ignore their markers.
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    text = text.replace("```text", "").replace("```", "")
    return text.strip()


# --- What the pull request touches -----------------------------------------


def is_doc(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        (path.startswith("docs/") and path.endswith(".md"))
        or name in ("README.md", "AGENTS.md")
        or path.startswith((".claude/rules/", ".claude/skills/"))
        or (path.startswith("frontend/app/rust/docs/") and name.endswith(".mdx"))
    )


def library_entries(library_ts: str) -> set[str]:
    """Component paths (relative to src/components) listed in library.ts."""
    body = library_ts.split("RUST_LIBRARY", 1)[-1].split("} as const", 1)[0]
    return set(LIBRARY_ENTRY.findall(body))


def rust_changes(changed: list[str], library_ts: list[str]) -> list[str]:
    """Changed files that are shared Rust components, tokens, or the list."""
    entries = set()
    for text in library_ts:
        entries |= library_entries(text)
    shared = {f"{COMPONENTS}{entry}.astro" for entry in entries}
    return sorted(
        path
        for path in changed
        if path == RUST_LIBRARY
        or path in shared
        or (path.startswith(COMPOSITIONS) and path.endswith(".astro"))
        or path.startswith(TOKENS)
    )


def path_tokens(path: str) -> set[str]:
    """How a doc may name `path`: in full, or relative to a known base."""
    tokens = {path}
    for base in PATH_BASES:
        if path.startswith(base):
            tokens.add(path[len(base) :])
    return {token for token in tokens if "/" in token}


def docs_naming(changed: list[str], docs: dict[str, str]) -> dict[str, list]:
    """{doc path: [changed files it names]} for docs not in the diff."""
    code = [path for path in changed if not is_doc(path)]
    found: dict[str, list] = {}
    for doc, text in docs.items():
        if doc in changed:
            continue
        named = [
            path
            for path in code
            if any(
                f"`{token}`" in text or f"({token})" in text
                for token in path_tokens(path)
            )
        ]
        if named:
            found[doc] = named
    return found


# --- The check -------------------------------------------------------------


def check(
    body: str,
    changed: list[str],
    library_ts: list[str],
    docs: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Return (errors, notices) for this description and diff."""
    errors: list[str] = []
    notices: list[str] = []
    found = sections(body)

    for heading in LABELS:
        if heading not in found:
            errors.append(
                f'The description has no "## {heading.title()}" section. '
                "Start from .github/pull_request_template.md."
            )
    if errors:
        return errors, notices

    _issue(errors, found["issue"])
    _review(
        errors,
        found["frontend review"],
        area="frontend",
        touched=[p for p in changed if p.startswith(FRONTEND_PREFIXES)],
        none_box="No website changes",
        ran_box="Ran the frontend review on the final diff",
        skill=".claude/skills/frontend-review/SKILL.md",
    )
    _review(
        errors,
        found["backend review"],
        area="backend",
        touched=[p for p in changed if p.startswith(BACKEND_PREFIXES)],
        none_box="No backend changes",
        ran_box="Ran the backend review on the final diff",
        skill=".claude/skills/backend-review/SKILL.md",
    )
    _rust(errors, found["rust component library"], changed, library_ts)
    _docs(errors, notices, found["documentation"], changed, docs)
    return errors, notices


def _issue(errors, section):
    text = field(section, "Issue", LABELS["issue"])
    no_issue = ticked(section, "No issue for this change")
    linked = CLOSES.search(text) or REFERS.search(text)
    if no_issue and CLOSES.search(text):
        errors.append(
            'Issue: "No issue for this change" is ticked, but the "Issue:" '
            "line closes one. Untick the box or drop the Closes line."
        )
    elif no_issue:
        if len(text) < MIN_REASON:
            errors.append(
                'Issue: say why there is no issue on the "Issue:" line (a '
                "Sentry fix, a help ticket link, a follow-up to #N)."
            )
    elif not linked:
        hint = (
            " A bare #123 doesn't say which: write Closes or Refs before it."
            if BARE_ISSUE.search(text)
            else ""
        )
        errors.append(
            'Issue: under "Issue:" write "Closes #123" when this pull '
            'request finishes the issue, or "Refs #123" when it is part of '
            'one; or tick "No issue for this change" and say why.' + hint
        )


def _review(errors, section, *, area, touched, none_box, ran_box, skill):
    if not touched:
        return
    sample = ", ".join(touched[:3]) + (" ..." if len(touched) > 3 else "")
    if ticked(section, none_box):
        errors.append(
            f'{area.title()} review: "{none_box}" is ticked, but the pull '
            f"request changes {sample}."
        )
    if not ticked(section, ran_box):
        errors.append(
            f'{area.title()} review: tick "{ran_box}" after running {skill} '
            f"(the pull request changes {sample})."
        )
    result = field(section, "Result", LABELS[f"{area} review"])
    if not result or PLACEHOLDER.search(result):
        errors.append(
            f"{area.title()} review: paste the review's result under " '"Result:".'
        )


def _rust(errors, section, changed, library_ts):
    touched = rust_changes(changed, library_ts)
    declared = ticked(section, "This pull request adds or changes a shared")
    if not touched and not declared:
        return
    labels = LABELS["rust component library"]
    if touched:
        sample = ", ".join(touched[:5]) + (" ..." if len(touched) > 5 else "")
        if ticked(section, "No shared component or token changed"):
            errors.append(
                'Rust: "No shared component or token changed" is ticked, '
                f"but the pull request changes {sample}."
            )
        if not declared:
            errors.append(
                'Rust: tick "This pull request adds or changes a shared '
                f'component or token" (the pull request changes {sample}).'
            )
    if not field(section, "Components / tokens", labels):
        errors.append(
            'Rust: name the components or tokens under "Components / tokens:".'
        )
    justification = field(section, "Human justification", labels)
    if len(justification) < MIN_JUSTIFICATION:
        errors.append(
            "Rust: a person must justify adding or changing a shared "
            'component or token under "Human justification:" (why the '
            "existing library could not be used as is). An agent records "
            "their words; it never writes them."
        )
    handle = HANDLE.search(field(section, "Justified by", labels))
    if not handle:
        errors.append(
            'Rust: put the GitHub handle of the person who justified it after "Justified by: @".'
        )
    elif AGENT_HANDLES.search(handle.group(1)):
        errors.append(
            f"Rust: @{handle.group(1)} is an agent or bot; the justification must come from a person."
        )


def _docs(errors, notices, section, changed, docs):
    updated = ticked(section, "Updated the docs this change affects")
    unchanged = ticked(section, "No documented behaviour changed")
    docs_changed = [path for path in changed if is_doc(path)]
    naming = docs_naming(changed, docs)
    if naming:
        listed = "; ".join(
            f"{doc} names {', '.join(paths[:3])}"
            for doc, paths in sorted(naming.items())[:10]
        )
        notices.append(f"Docs that name files this pull request changes: {listed}")
    if updated == unchanged:
        errors.append(
            'Documentation: tick exactly one of "Updated the docs this change '
            'affects" and "No documented behaviour changed".'
        )
        return
    reason = field(section, "Docs updated, or why none needed", LABELS["documentation"])
    if updated and not docs_changed:
        errors.append(
            'Documentation: "Updated the docs this change affects" is '
            "ticked, but no doc is in the diff (docs/, READMEs, "
            ".claude/rules, .claude/skills)."
        )
    if unchanged and naming and not docs_changed and not reason:
        errors.append(
            "Documentation: these docs name files the pull request changes: "
            f"{', '.join(sorted(naming)[:10])}. Update them, or say under "
            '"Docs updated, or why none needed:" why they are still right.'
        )


# --- Command line ----------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def _changed_files(base: str) -> list[str]:
    return [
        line
        for line in _git("diff", "--name-only", f"{base}...HEAD").splitlines()
        if line
    ]


def _library_versions(base: str) -> list[str]:
    versions = []
    head = ROOT / RUST_LIBRARY
    if head.exists():
        versions.append(head.read_text(encoding="utf-8"))
    try:
        versions.append(_git("show", f"{base}:{RUST_LIBRARY}"))
    except subprocess.CalledProcessError:
        pass
    return versions


def _current_docs() -> dict[str, str]:
    docs = {}
    for path in _git("ls-files", "*.md").splitlines():
        if not is_doc(path) or "/research/" in path or "/archive/" in path:
            continue
        try:
            docs[path] = (ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--base",
        default="origin/main",
        help="branch the pull request merges into",
    )
    parser.add_argument("--body-file", help="description file (default: $PR_BODY)")
    args = parser.parse_args(argv)

    if os.environ.get("PR_DRAFT") == "true":
        print(
            "::notice::Draft pull request: the checklist is checked when it is marked ready."
        )
        return 0

    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        body = os.environ.get("PR_BODY", "")

    errors, notices = check(
        body,
        _changed_files(args.base),
        _library_versions(args.base),
        _current_docs(),
    )

    for notice in notices:
        print(f"::notice::{notice}")
    for error in errors:
        print(f"::error::{error}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Pull request checklist\n\n")
            out.write(
                "\n".join(f"- ❌ {e}" for e in errors)
                or "- ✅ All controls that apply are filled in."
            )
            out.write("\n")
            if notices:
                out.write("\n" + "\n".join(f"- ℹ️ {n}" for n in notices) + "\n")
    if errors:
        print(
            f"\n{len(errors)} checklist item(s) to fix in the pull request description."
        )
        return 1
    print("Pull request checklist: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
