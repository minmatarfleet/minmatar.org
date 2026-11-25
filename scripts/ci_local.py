#!/usr/bin/env python3
"""Run the CI checks that apply to this branch's changes, locally.

CI (`.github/workflows/`) runs every check on every pull request. This
script reads the files the branch changes (against `origin/main`, including
uncommitted and untracked files) and runs only the checks those files
trigger, the same commands CI runs:

- backend-lint: black, flake8 and pylint on the changed backend files.
- backend-tests: the tests of the backend apps the diff changes, the apps
  that import them, and `app.tests` (the whole suite for a change outside
  an app, or with --full-backend / --all), plus the migration tests when a
  migration changed. A change outside `backend/` that backend tests read
  (docs, agent rules, the PR template, contract files) runs `app.tests`.
  Tests run on a fresh copy of a migrated template DB that never holds
  test data, so one run can't leave rows that break the next.
- bot: flake8 and the bot's unittest suite.
- voice: flake8 and the voice service's unittest suite (voice/).
- frontend-tests and frontend-types: vitest and the astro check ratchet.
  The type check is skipped when the website changes are only Markdown,
  public/ files or translation edits that remove no key.
- desktop: the desktop tests and the version check.
- agent-config: `.cursor/` is generated from `.claude/`.
- rust-browser (only with --rust): every story in Chromium.

It prints one line per check and, for a failure, the end of its output; the
full log is in the git directory, under ci_local/logs/. A tree that passed is remembered,
so running it again on the same files is free.

    python3 scripts/ci_local.py             # the checks this diff needs
    python3 scripts/ci_local.py --list      # what would run, and why
    python3 scripts/ci_local.py --all       # every check
    python3 scripts/ci_local.py --only backend-lint,frontend-types
    python3 scripts/ci_local.py --full-backend  # every backend test

The agent hooks (`scripts/agent_hooks.py`) run it before `git push` and
`gh pr create`. Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Migrated by ci_test_db.py and never tested on; each run gets a copy.
TEMPLATE_DB = ".test-db/template.sqlite3"
TEST_DB = ".test-db/run/test_db.sqlite3"
EXCERPT_LINES = 40

# Changes outside backend/ that backend tests read: docs (test_docs), the PR
# template and its checker, agent config, contract and schema files.
BACKEND_READS = (
    "docs/*",
    "*.md",
    ".claude/*",
    ".cursor/*",
    ".github/*",
    "scripts/*",
    "desktop/src/main/*",
    "desktop/test/contracts/*",
    "frontend/app/src/types/generated/openapi.json",
    "frontend/app/src/json/feature_gates.json",
)


# Backend paths that aren't one app's: a change here runs the whole suite.
BACKEND_SHARED = ("app", "fixtures", "templates", "sql", "scripts")
# Website changes the astro type check can't fail on.
FRONTEND_TEXT = (
    "frontend/app/*.md",
    "frontend/app/**/*.md",
    "frontend/app/**/*.mdx",
    "frontend/app/public/*",
)
I18N = "frontend/app/src/i18n/*.ts"
TRANSLATION_KEY = re.compile(r"^\s*['\"]([^'\"]+)['\"]\s*:")


def _git(*args: str, cwd: Path = ROOT, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _state_dir() -> Path:
    path = Path(_git("rev-parse", "--git-path", "ci_local").strip())
    if not path.is_absolute():
        path = ROOT / path
    (path / "logs").mkdir(parents=True, exist_ok=True)
    return path


def changed_files(base: str) -> list[str]:
    """Files that differ from the merge base, committed or not."""
    try:
        start = _git("merge-base", base, "HEAD").strip()
    except subprocess.CalledProcessError:
        start = base
    tracked = _git("diff", "--name-only", start).splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked) | set(untracked))


def tree_hash() -> str:
    """Hash of the working tree as git sees it (ignored files excluded)."""
    index = Path(_git("rev-parse", "--git-path", "index").strip())
    if not index.is_absolute():
        index = ROOT / index
    with tempfile.TemporaryDirectory() as tmp:
        tmp_index = Path(tmp) / "index"
        if index.exists():
            shutil.copyfile(index, tmp_index)  # keeps the stat cache
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        _git("add", "-A", env=env)
        return _git("write-tree", env=env).strip()


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


# --- Tool environments -------------------------------------------------------


def pipenv_bin(project: str, sync: bool = True) -> Path | None:
    """The bin/ of a pipenv project's venv, synced on first use."""
    cwd = ROOT / project
    env = {**os.environ, "PIPENV_VERBOSITY": "-1"}
    if not shutil.which("pipenv"):
        return None
    for attempt in (1, 2):
        found = subprocess.run(
            ["pipenv", "--venv"], cwd=cwd, env=env, capture_output=True
        )
        if found.returncode == 0:
            return Path(found.stdout.decode().strip()) / "bin"
        if not sync or attempt == 2 or not shutil.which("pipenv"):
            return None
        print(f"ci_local: creating the {project} virtualenv (pipenv sync)")
        subprocess.run(
            ["pipenv", "sync", "--dev"], cwd=cwd, env=env, capture_output=True
        )
    return None


NODE_MAJOR = 22  # .github/workflows/frontend.yml and desktop.yml


def _node_major(node: str) -> int:
    try:
        version = subprocess.run(
            [node, "--version"], capture_output=True, text=True
        ).stdout
        return int(version.strip().lstrip("v").split(".")[0])
    except (OSError, ValueError):
        return 0


def node_path() -> str:
    """PATH with a Node >= 22 first.

    Hooks run without the login shell, so nvm's Node is often not on PATH
    and an older system Node is.
    """
    path = os.environ.get("PATH", "")
    if _node_major(shutil.which("node") or "node") >= NODE_MAJOR:
        return path
    nvm = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
    found = []
    for bin_dir in (nvm / "versions" / "node").glob("v*/bin"):
        major = _node_major(str(bin_dir / "node"))
        if major >= NODE_MAJOR:
            # Prefer CI's major, then the newest.
            found.append((major != NODE_MAJOR, -major, str(bin_dir)))
    if not found:
        return path
    return min(found)[2] + os.pathsep + path


def _node_ready(project: str) -> list[list[str]]:
    """`npm ci` first when node_modules is missing."""
    if (ROOT / project / "node_modules" / ".bin").exists():
        return []
    return [["npm", "ci", "--no-audit", "--no-fund"]]


# --- Checks -----------------------------------------------------------------


@dataclass
class Check:
    name: str
    cwd: str
    steps: list[list[str]]
    why: str
    env: dict = field(default_factory=dict)
    before: object = None  # callable run before the steps
    after: object = None  # callable run after the steps, pass or fail
    excerpt: object = None  # callable(output) -> excerpt
    # Name in the pass cache; a partial run must not count as a full one.
    key: str = ""

    @property
    def cache_key(self) -> str:
        return self.key or self.name


def django_excerpt(output: str) -> str:
    """The FAIL/ERROR blocks and the summary of a Django test run."""
    lines = [
        line
        for line in output.splitlines()
        if not line.startswith(("Preserving test database", "Using existing"))
    ]
    # The parallel runner without tblib: "<test> failed:" ... "Unfortunately".
    blocks, keep = [], False
    for line in lines:
        if line.endswith(") failed:") or line.endswith(") raised an error:"):
            keep = True
        elif line.startswith("Unfortunately, tracebacks cannot be pickled"):
            keep = False
        if keep:
            blocks.append(line)
    if blocks:
        summary = [ln for ln in lines if ln.startswith(("Ran ", "FAILED"))]
        return "\n".join(blocks[: EXCERPT_LINES * 2] + summary)
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("=====")),
        None,
    )
    if start is None:
        return "\n".join(lines[-EXCERPT_LINES:])
    body = lines[start:]
    if len(body) > EXCERPT_LINES * 2:
        body = body[: EXCERPT_LINES * 2 - 5] + ["..."] + body[-4:]
    return "\n".join(body)


def _tail(output: str) -> str:
    return "\n".join(output.splitlines()[-EXCERPT_LINES:])


def _backend_python_files(changed: list[str]) -> list[str]:
    files = []
    for path in changed:
        if not (path.startswith("backend/") and path.endswith(".py")):
            continue
        if path.startswith("backend/scripts/") or "/migrations/" in path:
            continue
        if (ROOT / path).exists():
            files.append(path[len("backend/") :])
    return files


def _backend_apps(backend: Path) -> set[str]:
    return {
        p.name
        for p in backend.iterdir()
        if (p / "__init__.py").exists() and p.name not in BACKEND_SHARED
    }


FROM_IMPORT = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+\(?([\w\s,]+)", re.M)
PLAIN_IMPORT = re.compile(r"^\s*import\s+([\w.]+)", re.M)


def _module_of(backend: Path, path: str) -> str | None:
    """`eveonline.scopes` for backend/eveonline/scopes.py; None if not .py."""
    if not path.endswith(".py"):
        return None
    parts = path[len("backend/") : -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_module(backend: Path, dotted: str) -> bool:
    base = backend.joinpath(*dotted.split("."))
    return base.with_suffix(".py").exists() or (base / "__init__.py").exists()


def _imports(backend: Path, text: str) -> set[str]:
    """The modules a file imports, as precisely as the import names them.

    `from eveonline import scopes` is `eveonline.scopes`, not all of
    `eveonline`; `from eveonline.scopes import TokenType` is
    `eveonline.scopes`.
    """
    found = set(PLAIN_IMPORT.findall(text))
    for module, names in FROM_IMPORT.findall(text):
        subs = [
            f"{module}.{n}"
            for n in re.findall(r"\w+", names)
            if _is_module(backend, f"{module}.{n}")
        ]
        found.update(subs or [module])
    return found


def _importers(backend: Path, apps: set[str], modules: set[str]) -> set[str]:
    """The apps with a module importing one of modules, or its package."""

    def reaches(imported: str) -> bool:
        return any(
            imported == m
            or imported.startswith(m + ".")
            or m.startswith(imported + ".")
            for m in modules
        )

    found = set()
    for app in apps:
        for file in (backend / app).rglob("*.py"):
            if "migrations" in file.parts:
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
            if any(reaches(i) for i in _imports(backend, text)):
                found.add(app)
                break
    return found


def affected_backend_apps(
    changed: list[str], backend: Path | None = None
) -> list[str] | None:
    """Test labels for a backend change, or None for the whole suite.

    The apps the diff changes, the apps with a module importing a changed
    module (or a package holding one), and `app` (the repo-wide tests:
    docs, schema, hooks). A file outside an app (settings, Pipfile, the
    test runner, fixtures) can reach anything, so it runs everything, and
    so does a selection that is most of the suite anyway. GitHub CI still
    runs the whole suite on the pull request.
    """
    backend = backend or ROOT / "backend"
    apps = _backend_apps(backend)
    touched: set[str] = set()
    modules: set[str] = set()
    for path in changed:
        if not path.startswith("backend/"):
            continue
        parts = path.split("/")
        if len(parts) < 3 or parts[1] not in apps:
            return None
        touched.add(parts[1])
        module = _module_of(backend, path)
        if module and "migrations" not in parts:
            modules.add(module)
    if not touched:
        return None

    labels = touched | _importers(backend, apps - touched, modules)
    if len(labels) >= 0.75 * len(apps):
        return None
    return sorted(labels | {"app"})


def removed_translation_keys(paths: list[str], base: str) -> list[str]:
    """Translation keys the diff deletes from the i18n files."""
    try:
        start = _git("merge-base", base, "HEAD").strip()
        diff = _git("diff", "-U0", start, "--", *paths)
    except subprocess.CalledProcessError:
        return ["(could not diff)"]
    removed, added = set(), set()
    for line in diff.splitlines():
        if line.startswith(("---", "+++")):
            continue
        match = TRANSLATION_KEY.match(line[1:]) if line[:1] in "+-" else None
        if match:
            (removed if line[0] == "-" else added).add(match.group(1))
    return sorted(removed - added)


def frontend_types_needed(frontend: list[str], base: str) -> bool:
    """False when no website change can fail the astro type check."""
    if not frontend:
        return False
    i18n = [p for p in frontend if fnmatch.fnmatch(p, I18N)]
    other = [p for p in frontend if p not in i18n]
    if any(not _matches(p, FRONTEND_TEXT) for p in other):
        return True
    # t() takes a typed key, so deleting one can break a page.
    return bool(i18n) and bool(removed_translation_keys(i18n, base))


def _clear_worker_dbs() -> None:
    """Start the run on a fresh copy of the template, with no clones.

    --keepdb reuses whatever the last run left (rows, half-applied
    TransactionTestCase flushes, test_db_<n> clones), which is how one run
    broke the next with IntegrityErrors in unrelated tests. The template is
    only ever migrated (ci_test_db.py migrate), never tested on.
    """
    test_db = ROOT / "backend" / ".test-db"
    shutil.rmtree(test_db / "run", ignore_errors=True)
    # The pre-template cache, tested on directly; never trust it again.
    for old in test_db.glob("test_db*.sqlite3*"):
        old.unlink()


def _backend_tests(
    py: str,
    backend: list[str],
    reads: list[str],
    migrations: list[str],
    full: bool,
    run_all: bool,
) -> Check | None:
    """backend-tests: the affected apps (or everything) on a fresh DB."""
    test_env = {"TEST_DB_NAME": TEST_DB, "SETUP_TEST_DATA": ""}
    manage = [py, "manage.py", "test", "--settings=app.settings_test"]
    keep = ["--keepdb", "--noinput"]
    # The parallel workers' clones (test_db_1.sqlite3, ...) live in run/ too,
    # and --keepdb reuses them: clear the folder so they start fresh as well.
    fresh_db = [
        ["rm", "-rf", ".test-db/run"],
        ["mkdir", "-p", ".test-db/run"],
        [py, "ci_test_db.py", "check", TEMPLATE_DB],
        [py, "ci_test_db.py", "migrate", TEMPLATE_DB],
        [py, "ci_test_db.py", "record", TEMPLATE_DB],
        ["cp", TEMPLATE_DB, TEST_DB],
    ]
    if backend or run_all:
        labels = None if full else affected_backend_apps(backend)
        steps = [
            *fresh_db,
            [
                *manage,
                "--parallel",
                "auto",
                *keep,
                "--exclude-tag",
                "migration",
                *(labels or []),
            ],
        ]
        if labels:
            why = f"{len(backend)} backend files: {', '.join(labels)}"
        else:
            why = f"{len(backend)} backend files, whole suite"
        if migrations or run_all:
            steps.append([*manage, *keep, "--tag", "migration"])
            why += f", {len(migrations)} migrations"
        return Check(
            "backend-tests",
            "backend",
            steps,
            why,
            env=test_env,
            before=_clear_worker_dbs,
            excerpt=django_excerpt,
            key="backend-tests:" + ",".join(labels) if labels else "",
        )
    if reads:
        return Check(
            "backend-tests",
            "backend",
            [*fresh_db, [*manage, *keep, "app.tests"]],
            f"app.tests: {len(reads)} files backend tests read",
            env=test_env,
            before=_clear_worker_dbs,
            excerpt=django_excerpt,
            key="backend-tests:app.tests",
        )

    return None


def plan(
    changed: list[str],
    run_all: bool,
    rust: bool,
    venvs: dict,
    full_backend: bool = False,
    base: str = "origin/main",
) -> list[Check]:
    checks: list[Check] = []
    backend = [p for p in changed if p.startswith("backend/")]
    bot = [p for p in changed if p.startswith("bot/")]
    voice = [p for p in changed if p.startswith("voice/")]
    frontend = [p for p in changed if p.startswith("frontend/app/")]
    desktop = [p for p in changed if p.startswith("desktop/")]
    agent = [p for p in changed if p.startswith((".claude/", ".cursor/"))]
    reads = [p for p in changed if _matches(p, BACKEND_READS)]
    migrations = [p for p in backend if "/migrations/" in p]

    if agent or run_all:
        checks.append(
            Check(
                "agent-config",
                ".",
                [["python3", "scripts/sync_agent_config.py", "--check"]],
                f"{len(agent)} .claude/.cursor files",
            )
        )

    bin_ = venvs.get("backend")
    py = str(bin_ / "python") if bin_ else "python3"
    tool = (lambda name: str(bin_ / name)) if bin_ else (lambda name: name)

    lint_files = _backend_python_files(backend)
    if run_all:
        lint_files = ["."]
    if lint_files:
        checks.append(
            Check(
                "backend-lint",
                "backend",
                [
                    [tool("black"), "--check", "-q", *lint_files],
                    [tool("flake8"), *lint_files],
                    [tool("pylint"), "--rcfile=.pylintrc", *lint_files],
                ],
                "all of backend/" if run_all else f"{len(lint_files)} files",
            )
        )

    tests = _backend_tests(
        py, backend, reads, migrations, run_all or full_backend, run_all
    )
    if tests:
        checks.append(tests)

    if bot or run_all:
        bot_bin = venvs.get("bot")
        checks.append(
            Check(
                "bot",
                "bot",
                [
                    [tool("flake8"), "."],
                    [
                        str(bot_bin / "python") if bot_bin else "python3",
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                        "-t",
                        ".",
                    ],
                ],
                f"{len(bot)} bot files",
                env={
                    "DISCORD_BOT_TOKEN": "ci-placeholder",
                    "MINMATAR_API_TOKEN": "ci-placeholder",
                },
            )
        )

    if voice or run_all:
        checks.append(
            Check(
                "voice",
                "voice",
                [
                    [tool("flake8"), "--max-line-length", "100", "."],
                    ["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                ],
                f"{len(voice)} voice service files",
            )
        )

    if frontend or run_all:
        app = "frontend/app"
        why = f"{len(frontend)} frontend files"
        install = _node_ready(app)
        checks.append(
            Check(
                "frontend-tests",
                app,
                [*install, ["npm", "run", "test", "--", "--run"]],
                why,
            )
        )
        if run_all or frontend_types_needed(frontend, base):
            # Shares node_modules with frontend-tests: installs nothing.
            checks.append(
                Check("frontend-types", app, [["npm", "run", "check"]], why)
            )
            if install:
                # Run after the install above, not beside it.
                checks[-1].before = "frontend-tests"
        if rust:
            checks.append(
                Check(
                    "rust-browser",
                    app,
                    [["bash", "-c", RUST_BROWSER]],
                    "--rust",
                )
            )
            checks[-1].before = "frontend-tests"

    if desktop or run_all:
        checks.append(
            Check(
                "desktop",
                "desktop",
                [
                    *_node_ready("desktop"),
                    ["npm", "test"],
                    ["bash", "-c", DESKTOP_VERSION],
                ],
                f"{len(desktop)} desktop files",
            )
        )
    return checks


RUST_BROWSER = """
set -e
npx playwright install chromium >/dev/null
npm run rust:build
PORT=6017 npm run rust:serve-local > /tmp/ci_local_rust.log 2>&1 &
server=$!
trap 'kill $server' EXIT
for i in $(seq 1 90); do
  curl -fsS http://127.0.0.1:6017/rust/health > /dev/null && break
  sleep 2
done
npm run rust:test-browser -- http://127.0.0.1:6017/rust/
"""

# The same gate as .github/workflows/desktop.yml's "Version check".
DESKTOP_VERSION = """
base_version=$({ git show origin/main:desktop/package.json 2>/dev/null || true; } \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{try{console.log(JSON.parse(s).version)}catch(e){console.log('')}})")
if git diff --quiet origin/main -- src build package.json package-lock.json; then changed=false; else changed=true; fi
if ! released=$(gh release list --limit 200 --json tagName --jq '.[].tagName' 2>/dev/null); then
  echo "Version check skipped: gh could not list releases."
  exit 0
fi
node scripts/check_version.js pr "$base_version" "$changed" $(echo "$released" | grep '^v' || true)
"""


# --- Running ----------------------------------------------------------------


@dataclass
class Result:
    check: Check
    ok: bool
    seconds: float
    output: str
    command: str = ""


def run_check(check: Check, log_dir: Path) -> Result:
    started = time.monotonic()
    if callable(check.before):
        check.before()
    env = {
        **os.environ,
        "PIPENV_VERBOSITY": "-1",
        "PATH": node_path(),
        **check.env,
    }
    if check.env.get("SETUP_TEST_DATA") == "":
        env.pop("SETUP_TEST_DATA")
    output, failed = [], ""
    for step in check.steps:
        done = subprocess.run(
            step,
            cwd=ROOT / check.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
        output.append(done.stdout)
        if done.returncode != 0:
            failed = " ".join([Path(step[0]).name, *step[1:]])
            failed = " ".join(failed.split())[:160]
            break
    if callable(check.after):
        check.after()
    text = "".join(output)
    (log_dir / f"{check.name}.log").write_text(text, encoding="utf-8")
    return Result(check, not failed, time.monotonic() - started, text, failed)


def run(checks: list[Check], log_dir: Path) -> list[Result]:
    """Run the checks side by side; a check named in `before` goes first."""
    results: dict[str, Result] = {}
    first = [c for c in checks if not isinstance(c.before, str)]
    later = [c for c in checks if isinstance(c.before, str)]
    with ThreadPoolExecutor(max_workers=max(len(first), 1)) as pool:
        futures = {c.name: pool.submit(run_check, c, log_dir) for c in first}
        for name, future in futures.items():
            results[name] = future.result()
        for check in later:
            check.before = None
            results[check.name] = run_check(check, log_dir)
    return [results[c.name] for c in checks]


def _cache_path() -> Path:
    return _state_dir() / "passed.json"


def _load_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(tree: str, names: list[str]) -> None:
    cache = _load_cache()
    passed = set(cache.get(tree, []))
    # One tree is enough: the next run is on new files anyway.
    _cache_path().write_text(json.dumps({tree: sorted(passed | set(names))}))


def report(results: list[Result], log_dir: Path) -> str:
    lines = []
    for r in results:
        status = "ok  " if r.ok else "FAIL"
        lines.append(f"  {status} {r.check.name:<15} {r.seconds:5.0f}s")
    for r in results:
        if r.ok:
            continue
        excerpt = (r.check.excerpt or _tail)(r.output)
        log = log_dir / f"{r.check.name}.log"
        lines.append("")
        lines.append(f"--- {r.check.name}: `cd {r.check.cwd} && {r.command}`")
        lines.append(excerpt.rstrip())
        lines.append(f"(full log: {log})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--all", action="store_true", help="every check")
    parser.add_argument("--only", help="comma-separated check names")
    parser.add_argument("--list", action="store_true", help="plan only")
    parser.add_argument("--rust", action="store_true", help="add Rust stories")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--full-backend",
        action="store_true",
        help="every backend test, not only the affected apps'",
    )
    args = parser.parse_args(argv)

    changed = changed_files(args.base)
    needs_backend = args.all or any(
        p.startswith("backend/") or _matches(p, BACKEND_READS) for p in changed
    )
    venvs = {}
    if not args.list:
        if needs_backend or any(p.startswith("bot/") for p in changed):
            venvs["backend"] = pipenv_bin("backend")
        if args.all or any(p.startswith("bot/") for p in changed):
            venvs["bot"] = pipenv_bin("bot")
        missing = [name for name, path in venvs.items() if path is None]
        if missing:
            # One line, not a traceback: this goes back to an agent.
            print(
                "ci_local: no virtualenv for "
                + ", ".join(missing)
                + (
                    ". Run `pipenv sync --dev` there."
                    if shutil.which("pipenv")
                    else ". pipenv isn't installed: `pip install pipenv`, "
                    "then `pipenv sync --dev` there."
                )
            )
            return 1
    checks = plan(
        changed, args.all, args.rust, venvs, args.full_backend, args.base
    )
    if args.only:
        wanted = set(args.only.split(","))
        checks = [c for c in checks if c.name in wanted]
        for c in checks:
            if isinstance(c.before, str) and c.before not in wanted:
                c.before = None

    if args.list:
        print(f"{len(changed)} changed files against {args.base}")
        for c in checks:
            print(f"  {c.name:<15} {c.why}")
        return 0
    if not checks:
        print("ci_local: no checks apply to these changes.")
        return 0

    tree = tree_hash()
    if not args.no_cache:
        passed = set(_load_cache().get(tree, []))
        # A full pass covers a partial one, not the other way round.
        done = [c for c in checks if passed & {c.name, c.cache_key}]
        skipped = done
        checks = [c for c in checks if c not in done]
        if not checks:
            names = ", ".join(c.name for c in skipped)
            print(f"ci_local: already passed on these files ({names}).")
            return 0

    log_dir = _state_dir() / "logs"
    results = run(checks, log_dir)
    _save_cache(tree, [r.check.cache_key for r in results if r.ok])
    failed = [r for r in results if not r.ok]
    header = "failed" if failed else "passed"
    print(f"ci_local: {header} ({len(changed)} changed files)")
    print(report(results, log_dir))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
