"""Golden payloads shared with the clients that read them.

A contract test seeds data, calls a real endpoint, and compares the JSON with
a committed file that the client's own tests render from:

- ``desktop/test/contracts/*.json``: what installed desktop versions parse.
  Desktop CI runs whenever one of these files changes.
- ``frontend/app/testing/contracts/*.json``: what the website renders.

So a backend change that renames, retypes or drops a field fails here, on
the PR that makes it, instead of in a released app. If the change is
intended (and additive, see .claude/rules/desktop-release.md), regenerate:

    UPDATE_CONTRACTS=1 python manage.py test <the contract test>

and commit the files. Contract data is made up in the test; never put real
pilots, tokens or Discord names in it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

REPO = Path(settings.BASE_DIR).resolve().parent
DESKTOP = REPO / "desktop" / "test" / "contracts"
WEB = REPO / "frontend" / "app" / "testing" / "contracts"

# Contract data is seeded against a fixed clock, so dates, campaign weeks and
# "x minutes ago" come out the same on every run. A Saturday evening: the
# campaign week (Thursday 11:00 UTC) is two days old.
FIXED_NOW = datetime(2026, 1, 17, 18, 0, tzinfo=dt_timezone.utc)


def frozen_clock(now: datetime = FIXED_NOW):
    """Patch django.utils.timezone.now for the contract's seed and request."""
    return mock.patch("django.utils.timezone.now", return_value=now)


def updating() -> bool:
    return os.environ.get("UPDATE_CONTRACTS") == "1"


def render(payload) -> str:
    plain = json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
    return (
        json.dumps(plain, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def check(testcase, path: Path, payload) -> None:
    """Fail unless ``payload`` matches the committed file at ``path``."""
    text = render(payload)
    testcase.maxDiff = None
    if updating():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    if not path.exists():
        testcase.fail(
            f"{path.relative_to(REPO)} is missing: run the test with "
            "UPDATE_CONTRACTS=1 and commit it"
        )
    testcase.assertEqual(
        json.loads(path.read_text(encoding="utf-8")),
        json.loads(text),
        f"{path.relative_to(REPO)} no longer matches the endpoint. Clients "
        "read this payload; if the change is intended and additive, rerun "
        "with UPDATE_CONTRACTS=1 and commit the file.",
    )
