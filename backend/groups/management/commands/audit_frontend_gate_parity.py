"""Count who a switch from legacy gates to pilot features would change.

Read-only. Run against production with --database production_readonly
before setting FRONTEND_GATE_SOURCE=features. Exits non-zero when any user
would lose a gate whose parity class doesn't allow it.
"""

import json
from contextlib import contextmanager

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from groups.features.gate_manifest import LOSS_ALLOWED_PARITY, load_gates
from groups.helpers.feature_access import (
    clear_feature_cache,
    get_user_feature_codes,
)
from tribes.models import TribeGroupMembership
from users.helpers import get_user_permissions

SAMPLE_SIZE = 10


class _AllQueriesTo:
    """Router that sends every query to one alias."""

    def __init__(self, alias):
        self.alias = alias

    def db_for_read(self, model, **hints):
        return self.alias

    def db_for_write(self, model, **hints):
        return self.alias

    def allow_relation(self, obj1, obj2, **hints):
        return True


@contextmanager
def _use_database(alias):
    if alias == "default":
        yield
        return
    routers = router.routers
    routers.insert(0, _AllQueriesTo(alias))
    clear_feature_cache()
    try:
        yield
    finally:
        routers.pop(0)
        clear_feature_cache()


def _thinkspeak_member_ids() -> set[int]:
    """Users the content pages' is_thinkspeak_member() check lets in."""
    return set(
        TribeGroupMembership.objects.filter(
            status=TribeGroupMembership.STATUS_ACTIVE,
            tribe_group__tribe__slug="pulse",
            tribe_group__code="pulse.thinkspeak",
        ).values_list("user_id", flat=True)
    )


def audit(gates, users):
    """Per gate: users who'd gain or lose it under features."""
    thinkspeak = _thinkspeak_member_ids()
    report = {
        gate.key: {
            "feature": gate.feature,
            "parity": gate.parity,
            "gains": [],
            "losses": [],
        }
        for gate in gates
    }
    for user in users:
        permissions = set(get_user_permissions(user.id))
        features = set(get_user_feature_codes(user))
        for gate in gates:
            if gate.custom:
                legacy = user.is_superuser or user.id in thinkspeak
            else:
                legacy = gate.legacy_allows(permissions, user.is_superuser)
            feature = gate.feature in features
            if feature and not legacy:
                report[gate.key]["gains"].append(user.id)
            elif legacy and not feature:
                report[gate.key]["losses"].append(user.id)
    return report


class Command(BaseCommand):
    help = (
        "Compare legacy permission gates with pilot features for every "
        "active user. Read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to read from (e.g. production_readonly).",
        )
        parser.add_argument(
            "--manifest",
            default=None,
            help="Path to feature_gates.json (defaults to the repo copy).",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Write the full report, with user ids, to this JSON file.",
        )

    def handle(self, *args, **options):
        gates = load_gates(options["manifest"])
        with _use_database(options["database"]):
            users = list(User.objects.filter(is_active=True).order_by("id"))
            report = audit(gates, users)

        unexpected_losses = []
        self.stdout.write(
            f"{len(users)} active users, {len(gates)} gates "
            f"({options['database']})"
        )
        for key, row in report.items():
            gains, losses = len(row["gains"]), len(row["losses"])
            if not gains and not losses:
                continue
            flag = ""
            if losses and row["parity"] not in LOSS_ALLOWED_PARITY:
                unexpected_losses.append(key)
                flag = "  UNEXPECTED LOSS"
            self.stdout.write(
                f"{key:<40} +{gains:<5} -{losses:<5} "
                f"[{row['parity'] or 'exact'}]{flag}"
            )
            if losses:
                self.stdout.write(
                    f"    losses e.g. {row['losses'][:SAMPLE_SIZE]}"
                )

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
            self.stdout.write(f"Full report written to {options['output']}")

        if unexpected_losses:
            raise CommandError(
                "Users would lose access on: " + ", ".join(unexpected_losses)
            )
        self.stdout.write(self.style.SUCCESS("No unexpected losses."))
