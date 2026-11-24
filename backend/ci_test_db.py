"""
Keep CI's cached, migrated test database safe to reuse.

CI restores the newest cached test DB even when migrations have changed
since, and `manage.py test --keepdb` then applies only the new ones. That
is only correct while every migration already in the DB is still on disk
unchanged. A renumbered, edited or squashed migration would leave the
cached schema out of step with the code, so `check` deletes the DB and
the run migrates from scratch.

    python ci_test_db.py check .test-db/test_db.sqlite3
    python ci_test_db.py record .test-db/test_db.sqlite3
    python ci_test_db.py migrate .test-db/template.sqlite3

`migrate` creates the DB or applies the new migrations, and runs no tests:
scripts/ci_local.py keeps a template that only ever gets migrations and
runs each test run on a copy, so test data never reaches the cache.

`record` writes `<db>.manifest.json`: a hash of every migration file that
the DB has been migrated with. Run it after the tests, before saving the
cache. `check` runs after restoring it.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
SKIP_DIRS = {"node_modules", ".venv", "venv"}


def migration_hashes() -> dict[str, str]:
    hashes = {}
    for path in sorted(BACKEND.glob("**/migrations/*.py")):
        rel = path.relative_to(BACKEND)
        if SKIP_DIRS & set(rel.parts):
            continue
        hashes[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def manifest_path(db: Path) -> Path:
    return db.with_name(db.name + ".manifest.json")


def stale_reasons(recorded: dict[str, str], current: dict[str, str]):
    for name, digest in sorted(recorded.items()):
        if name not in current:
            yield f"{name} was removed or renamed"
        elif current[name] != digest:
            yield f"{name} was edited"


def check(db: Path) -> None:
    manifest = manifest_path(db)
    if not db.exists():
        print("No cached test DB: migrating from scratch.")
        return
    reasons = []
    if not manifest.exists():
        reasons = ["the cached DB has no migration manifest"]
    else:
        recorded = json.loads(manifest.read_text(encoding="utf-8"))
        reasons = list(stale_reasons(recorded, migration_hashes()))
    if reasons:
        print("Discarding the cached test DB:")
        for reason in reasons[:20]:
            print(f"  {reason}")
        db.unlink()
        manifest.unlink(missing_ok=True)
        return
    new = len(migration_hashes()) - len(recorded)
    print(f"Reusing the cached test DB; {new} new migration file(s).")


def record(db: Path) -> None:
    if not db.exists():
        print(f"{db} does not exist; nothing to record.")
        return
    manifest_path(db).write_text(
        json.dumps(migration_hashes(), indent=1, sort_keys=True),
        encoding="utf-8",
    )


def migrate(db: Path) -> None:
    """Create the test DB at db, or bring it up to date. No tests run."""
    os.environ["DJANGO_SETTINGS_MODULE"] = "app.settings_test"
    os.environ["TEST_DB_NAME"] = str(db)
    os.environ.pop("SETUP_TEST_DATA", None)
    # Django reads the settings module on import: after the environment.
    import django  # pylint: disable=import-outside-toplevel
    from django.db import (  # pylint: disable=import-outside-toplevel
        connection,
    )

    django.setup()
    connection.creation.create_test_db(
        verbosity=0, autoclobber=True, serialize=False, keepdb=True
    )


COMMANDS = {"check": check, "record": record, "migrate": migrate}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    COMMANDS[argv[1]](Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
