"""Docs must describe the code that is in the repo.

Cheap checks that catch the drift that has bitten us: docs naming deleted
files or management commands, an index that misses a doc, the Cursor copy of
the agent rules falling behind `.claude/`, and reference tables that no
longer match the code they describe.

They read the checkout, so they skip when only `backend/` is present (the
backend Docker image).
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

from django.core.management import get_commands

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs"
HAS_REPO = (DOCS / "README.md").exists()

# Places a relative path in a doc may be relative to, besides the doc's own
# folder: `groups/...` means backend/groups, `src/...` frontend/app/src, ...
PATH_BASES = (
    "",
    "backend",
    "frontend/app",
    "frontend/app/src",
    "frontend/app/src/components",
    "frontend/app/src/components/blocks",
    "desktop",
    "mobile",
    "bot",
)
FRONTEND_ALIASES = {
    "@components/": "frontend/app/src/components/",
    "@helpers/": "frontend/app/src/helpers/",
    "@dtypes/": "frontend/app/src/types/",
    "@json/": "frontend/app/src/json/",
    "@layouts/": "frontend/app/src/layouts/",
    "@i18n/": "frontend/app/src/i18n/",
    "@markdown/": "frontend/app/src/markdown/",
    "@/": "frontend/app/src/",
}
PATH_SUFFIXES = tuple(
    (
        ".py .md .mdc .astro .ts .tsx .js .mjs .cjs .json .yml .yaml .sh"
        " .scss .css .html .toml .cfg .ini .txt .ps1 .png .jar .example"
        " .lock .conf /"
    ).split()
)
# Local caches, build output and gitignored local files that docs mention
# but a CI checkout doesn't have.
UNTRACKED_PARTS = (
    ".cache/",
    "dist/",
    ".reddit-mcp/",
    "node_modules/",
    ".test-db/",
)
UNTRACKED_FILES = ("app/settings.py",)
# Third-party code a doc quotes; not ours to keep in the repo.
EXTERNAL_PATHS = {
    ("docs/desktop/overlay-technology.md", "Programm-Quellcode/src/main.js"),
}
EXTENSIONLESS_IMPORT = (".ts", ".astro", ".js", ".json", "/index.ts")

BACKTICK = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"```.*?```", re.S)
ALIAS_IMPORT = re.compile(r"""['"](@[a-z0-9]*/[^'"\s]+)['"]""")
MANAGE_PY = re.compile(r"(?:python3?\s+|\./)manage\.py\s+([a-z_][a-z0-9_]*)")
INDEX_LINK = re.compile(r"\]\(([^)#\s]+\.md)\)")


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _index_status() -> dict[str, str]:
    """docs/README.md rows: {path relative to docs/: status}."""
    status = {}
    for line in _read(DOCS / "README.md").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        link = INDEX_LINK.search(cells[0])
        if link:
            status[link.group(1)] = cells[1]
    return status


def _doc_files() -> list[Path]:
    """Every doc under docs/ except the index and research notes."""
    return sorted(
        path
        for path in DOCS.rglob("*.md")
        if path != DOCS / "README.md"
        and "research" not in path.relative_to(DOCS).parts
    )


def _current_docs() -> list[Path]:
    """Docs that must match the code: not historical, plus READMEs/rules."""
    historical = {
        DOCS / rel
        for rel, status in _index_status().items()
        if status == "historical"
    }
    files = [path for path in _doc_files() if path not in historical]
    patterns = (
        "README.md",
        "*/README.md",
        "*/*/README.md",
        "backend/*/README.md",
        "backend/*/*/README.md",
        "*/AGENTS.md",
        "*/*/AGENTS.md",
        ".claude/rules/*.md",
        ".claude/skills/*/*.md",
    )
    for pattern in patterns:
        files.extend(
            path
            for path in REPO.glob(pattern)
            if "node_modules" not in path.parts
        )
    return sorted(set(files))


def _path_exists(doc: Path, token: str) -> bool:
    for alias, target in FRONTEND_ALIASES.items():
        if token.startswith(alias):
            base = REPO / (target + token[len(alias) :])
            return base.exists() or any(
                Path(f"{base}{suffix}").exists()
                for suffix in EXTENSIONLESS_IMPORT
            )
    candidates = [doc.parent / token] + [
        REPO / base / token for base in PATH_BASES
    ]
    return any(candidate.exists() for candidate in candidates)


def _looks_like_repo_path(token: str) -> bool:
    if "/" not in token or token.startswith("/") or "://" in token:
        return False
    if any(char in token for char in " *<>{}$…|\\%~?=()[],") or "..." in token:
        return False
    if not token.endswith(PATH_SUFFIXES):
        return False
    if any(part in token for part in UNTRACKED_PARTS):
        return False
    if token.endswith(UNTRACKED_FILES):
        return False
    first = token.split("/", 1)[0]
    # my.minmatar.org/..., docs.expo.dev/...: a URL without its scheme.
    return not ("." in first.strip(".") and not first.startswith("."))


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class DocsMatchCodeTest(unittest.TestCase):
    def test_every_doc_is_in_the_index(self):
        indexed = set(_index_status())
        missing = [
            str(path.relative_to(DOCS))
            for path in _doc_files()
            if str(path.relative_to(DOCS)) not in indexed
        ]
        self.assertEqual(missing, [], "add these to docs/README.md")

    def test_index_links_point_at_files(self):
        broken = [rel for rel in _index_status() if not (DOCS / rel).exists()]
        self.assertEqual(broken, [])

    def test_repo_paths_in_docs_exist(self):
        missing = []
        for doc in _current_docs():
            text = _read(doc)
            rel_doc = str(doc.relative_to(REPO))
            for match in BACKTICK.finditer(FENCE.sub("", text)):
                token = match.group(1).strip().rstrip(".,:;")
                if not _looks_like_repo_path(token):
                    continue
                if (rel_doc, token) in EXTERNAL_PATHS:
                    continue
                if not _path_exists(doc, token):
                    missing.append(f"{rel_doc}: {token}")
            for match in ALIAS_IMPORT.finditer(text):
                token = match.group(1)
                if token.split("/", 1)[0] + "/" not in FRONTEND_ALIASES:
                    continue
                if not _path_exists(doc, token):
                    missing.append(f"{rel_doc}: {token}")
        self.assertEqual(missing, [], "docs name paths that don't exist")

    def test_manage_py_commands_in_docs_exist(self):
        commands = set(get_commands())
        unknown = []
        files = _current_docs() + sorted(REPO.glob(".claude/skills/**/*.py"))
        for doc in files:
            for match in MANAGE_PY.finditer(_read(doc)):
                if match.group(1) not in commands:
                    unknown.append(
                        f"{doc.relative_to(REPO)}: {match.group(1)}"
                    )
        self.assertEqual(unknown, [], "docs name unknown manage.py commands")

    def test_cursor_config_is_generated_from_claude(self):
        spec = importlib.util.spec_from_file_location(
            "sync_agent_config", REPO / "scripts" / "sync_agent_config.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.drift(REPO),
            [],
            "edit .claude/ and run `python3 scripts/sync_agent_config.py`",
        )

    def test_compositions_table_matches_the_directory(self):
        text = _read(DOCS / "frontend-design.md")
        section = text.split("## 4. Layout methodology", 1)[1]
        section = section.split("\n## ", 1)[0]
        documented = set(re.findall(r"^\| `(\w+)` \|", section, re.M))
        present = {
            path.stem
            for path in (
                REPO / "frontend/app/src/components/compositions"
            ).glob("*.astro")
        }
        self.assertEqual(documented, present)

    def test_desktop_readme_lists_every_main_module(self):
        readme = _read(REPO / "desktop" / "README.md")
        main = REPO / "desktop" / "src" / "main"
        missing = [
            path.name
            for path in sorted(main.glob("*.js"))
            if f"src/main/{path.name}" not in readme
        ]
        self.assertEqual(missing, [], "add these to desktop/README.md")

    def test_mobile_agents_names_the_installed_expo_sdk(self):
        package = json.loads(_read(REPO / "mobile" / "package.json"))
        major = re.search(r"\d+", package["dependencies"]["expo"]).group(0)
        agents = _read(REPO / "mobile" / "AGENTS.md")
        self.assertEqual(
            set(re.findall(r"docs\.expo\.dev/versions/v(\d+)", agents)),
            {major},
        )

    def test_campaigns_readme_lists_the_confirmed_event_codes(self):
        # pylint: disable-next=import-outside-toplevel
        from campaigns.constants import EVENT_CODE_SEED

        readme = _read(REPO / "backend" / "campaigns" / "README.md")
        paragraph = readme.split("**Unconfirmed event codes never score.**")
        paragraph = paragraph[1].split("\n- **", 1)[0]
        confirmed = {
            str(row["event_code"])
            for row in EVENT_CODE_SEED
            if row["confirmed"]
        }
        self.assertEqual(
            confirmed - set(re.findall(r"\d{3}", paragraph)), set()
        )

    def test_lp_buyback_doc_constants_exist(self):
        # pylint: disable=import-outside-toplevel
        from industry.helpers import (
            lp_buyback_sweep,
            lp_market_orders,
            lp_order_stats,
        )

        text = _read(DOCS / "industry" / "lp-buyback.md")
        names = set(re.findall(r"`([A-Z][A-Z0-9_]{3,})`", text))
        modules = (lp_buyback_sweep, lp_market_orders, lp_order_stats)
        missing = sorted(
            name
            for name in names
            if not any(hasattr(module, name) for module in modules)
        )
        self.assertEqual(missing, [])
