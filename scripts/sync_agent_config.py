#!/usr/bin/env python3
"""Generate the Cursor agent config from the Claude Code one.

`.claude/` is the source of truth for agent rules and skills. Cursor reads
`.cursor/rules/*.mdc` and `.cursor/skills/`, so this script writes those from
`.claude/`:

- `.claude/rules/<name>.md` -> `.cursor/rules/<name>.mdc`. The body is copied
  as is. The Cursor frontmatter is built from the rule's `paths:` list
  (`globs`, `alwaysApply: false`); a rule without `paths:` gets
  `alwaysApply: true`. The `description` (and `globs` on an always-on rule)
  are Cursor-only, so they are kept from the existing `.mdc`, or taken from
  the rule's first heading for a new one.
- `.claude/skills/**` -> `.cursor/skills/**`, byte for byte. Paths inside the
  skills point at `.claude/skills/...`, which exists in every checkout.

Edit `.claude/`, never `.cursor/rules` or `.cursor/skills`, then run:

    python3 scripts/sync_agent_config.py          # write .cursor/
    python3 scripts/sync_agent_config.py --check  # exit 1 on drift

`backend/app/tests/test_docs.py` runs the check in CI. Standard library only.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_RULES = Path(".claude/rules")
CLAUDE_SKILLS = Path(".claude/skills")
CURSOR_RULES = Path(".cursor/rules")
CURSOR_SKILLS = Path(".cursor/skills")


def _read(path: Path) -> str:
    # Not read_text(): keep line endings exactly as committed.
    return path.read_bytes().decode("utf-8")


def _split_frontmatter(text: str) -> tuple[list[str], str]:
    """Return (frontmatter lines, body) for a file that may start with ---."""
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 4)
    if end == -1:
        return [], text
    return text[4:end].split("\n"), text[end + len("\n---\n") :]


def _claude_paths(frontmatter: list[str]) -> list[str]:
    paths: list[str] = []
    in_paths = False
    for line in frontmatter:
        if line.startswith("paths:"):
            in_paths = True
            continue
        if in_paths and line.lstrip().startswith("- "):
            paths.append(line.lstrip()[2:].strip().strip("\"'"))
            continue
        in_paths = False
    return paths


def _cursor_fields(frontmatter: list[str]) -> dict[str, str]:
    fields = {}
    for line in frontmatter:
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def render_rule(claude_text: str, existing_mdc: str | None) -> str:
    """Return the .mdc text for one .claude rule."""
    claude_fm, body = _split_frontmatter(claude_text)
    paths = _claude_paths(claude_fm)
    old = _cursor_fields(_split_frontmatter(existing_mdc or "")[0])
    lines = [f"description: {old.get('description') or _first_heading(body)}"]
    if paths:
        lines.append(f"globs: {','.join(paths)}")
        lines.append("alwaysApply: false")
    else:
        if old.get("globs"):
            lines.append(f"globs: {old['globs']}")
        lines.append("alwaysApply: true")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body.lstrip("\n")


def expected_files(root: Path = ROOT) -> dict[Path, bytes]:
    """Map each generated .cursor path (relative to root) to its content."""
    expected: dict[Path, bytes] = {}
    for rule in sorted((root / CLAUDE_RULES).glob("*.md")):
        target = CURSOR_RULES / f"{rule.stem}.mdc"
        existing = root / target
        current = _read(existing) if existing.exists() else None
        expected[target] = render_rule(_read(rule), current).encode()
    skills = root / CLAUDE_SKILLS
    for source in sorted(skills.rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts:
            rel = source.relative_to(skills)
            expected[CURSOR_SKILLS / rel] = source.read_bytes()
    return expected


def _generated_now(root: Path) -> set[Path]:
    found = {p.relative_to(root) for p in (root / CURSOR_RULES).glob("*.mdc")}
    skills = root / CURSOR_SKILLS
    if skills.exists():
        found |= {
            p.relative_to(root)
            for p in skills.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
    return found


def drift(root: Path = ROOT) -> list[str]:
    """Return one message per .cursor file that differs from .claude."""
    expected = expected_files(root)
    problems = []
    for rel, content in expected.items():
        path = root / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
        elif path.read_bytes() != content:
            problems.append(f"differs: {rel}")
    for rel in sorted(_generated_now(root) - set(expected)):
        problems.append(f"no .claude source: {rel}")
    return problems


def sync(root: Path = ROOT) -> list[str]:
    """Write .cursor/ from .claude/ and return what changed."""
    changed = drift(root)
    expected = expected_files(root)
    for rel, content in expected.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
    for rel in _generated_now(root) - set(expected):
        (root / rel).unlink()
    return changed


def main(argv: list[str]) -> int:
    if "--check" in argv:
        problems = drift()
        for problem in problems:
            print(problem)
        if problems:
            print(
                "\n.cursor/ is out of date. Edit .claude/ and run "
                "`python3 scripts/sync_agent_config.py`."
            )
            return 1
        return 0
    for change in sync():
        print(change)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
