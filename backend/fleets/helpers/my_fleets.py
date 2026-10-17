"""
The desktop fleet window's Recent tab and the user's ship sign-ups.

Recent: the fleets the user flew in or commanded in the last 30 days, with
the fleet's kills and losses and, per loss of theirs, the SRP state. It is
the place a closed loss card or a finished fleet goes, so "SRP not filed"
stays one click away. Cached per user for a minute; the kill numbers come
from the stored fleet_kills rollup for finished fleets.

Sign-ups: which upcoming fleets the user put a character down for, so the
schedule can say "signed up" and the Fleet tab can show their next fleet.
Not cached: it is one query and changes on a click.
"""

from datetime import timedelta

from django.utils import timezone

from eveonline.helpers.corporations.safe_cache import cache_get, cache_set
from eveonline.models import EveCharacter
from feed.helpers.fleet_kills import fleet_kill_report
from fleets.helpers.fleet_window import TYPE_LABELS

RECENT_DAYS = 30
RECENT_LIMIT = 12
RECENT_CACHE_SECONDS = 60
# A fleet stays in the schedule (and its sign-ups count) this long after
# its start time, so a late form-up still shows.
SIGNUP_GRACE = timedelta(hours=12)


def _recent_key(user_id: int) -> str:
    return f"fleets:window:recent:{user_id}"


def _title(fleet) -> str:
    if fleet.doctrine:
        return fleet.doctrine.name
    return TYPE_LABELS.get(fleet.type, "Fleet") + " fleet"


def _recent_fleets(user, mine: set[int]) -> list:
    # pylint: disable=import-outside-toplevel
    from fleets.models import (
        EveFleet,
        EveFleetInstance,
        EveFleetInstanceMember,
    )

    since = timezone.now() - timedelta(days=RECENT_DAYS)
    flown = set(
        EveFleetInstanceMember.objects.filter(
            character_id__in=mine,
            eve_fleet_instance__start_time__gte=since,
        ).values_list("eve_fleet_instance__eve_fleet_id", flat=True)
    )
    commanded = set(
        EveFleetInstance.objects.filter(
            eve_fleet__created_by=user, start_time__gte=since
        ).values_list("eve_fleet_id", flat=True)
    )
    ids = flown | commanded
    if not ids:
        return []
    latest = {}
    for instance in EveFleetInstance.objects.filter(
        eve_fleet_id__in=ids
    ).order_by("start_time"):
        latest[instance.eve_fleet_id] = instance
    order = sorted(ids, key=lambda i: latest[i].start_time, reverse=True)
    fleets = EveFleet.objects.select_related("doctrine").in_bulk(
        order[:RECENT_LIMIT]
    )
    return [
        (fleets[i], latest[i], i in commanded)
        for i in order[:RECENT_LIMIT]
        if i in fleets
    ]


def recent_fleets(user) -> dict:
    """The Recent tab: last fleets, newest first, and SRP still owed."""
    # pylint: disable=import-outside-toplevel
    from srp.models import EveFleetShipReimbursement

    cached = cache_get(_recent_key(user.id))
    if cached is not None:
        return cached

    mine = set(
        EveCharacter.objects.filter(user=user).values_list(
            "character_id", flat=True
        )
    )
    rows = []
    for fleet, instance, was_fc in _recent_fleets(user, mine):
        report = fleet_kill_report(fleet)
        losses = [
            row
            for row in report["killmails"]
            if row["outcome"] == "loss"
            and not row.get("is_capsule")
            and row.get("victim_character_id") in mine
        ]
        rows.append(
            {
                "fleet_id": fleet.id,
                "title": _title(fleet),
                "type_label": TYPE_LABELS.get(fleet.type, fleet.type),
                "started_at": instance.start_time,
                "ended_at": instance.end_time,
                "live": instance.end_time is None,
                "was_fc": was_fc,
                "kills": report["ships_destroyed"],
                "losses": report["ships_lost"],
                "isk_destroyed": report["isk_destroyed"],
                "isk_lost": report["isk_lost"],
                "aar_link": fleet.aar_link or None,
                "my_losses": [
                    {
                        "killmail_id": row["killmail_id"],
                        "killmail_time": row["killmail_time"],
                        "ship_type_id": row.get("victim_ship_type_id"),
                        "ship_name": row.get("victim_ship_name") or "",
                        "isk_value": row.get("isk_value") or 0,
                        "solar_system_name": row.get("solar_system_name")
                        or "",
                    }
                    for row in losses
                ],
            }
        )

    killmail_ids = [
        loss["killmail_id"] for row in rows for loss in row["my_losses"]
    ]
    srp = {}
    for killmail_id, status, amount in (
        EveFleetShipReimbursement.objects.filter(killmail_id__in=killmail_ids)
        .exclude(status="withdrawn")
        .values_list("killmail_id", "status", "amount")
    ):
        srp[killmail_id] = (status, amount)
    owed = 0
    for row in rows:
        for loss in row["my_losses"]:
            status, amount = srp.get(loss["killmail_id"], ("none", 0))
            loss["srp_status"] = status
            loss["srp_amount"] = int(amount or 0)
            owed += status == "none"

    result = {"fleets": rows, "srp_owed": owed}
    cache_set(_recent_key(user.id), result, RECENT_CACHE_SECONDS)
    return result


def forget_recent_fleets(user_id: int) -> None:
    # pylint: disable=import-outside-toplevel
    from eveonline.helpers.corporations.safe_cache import cache_delete

    cache_delete(_recent_key(user_id))


def my_signups(user) -> list[dict]:
    """The user's ship sign-ups for fleets that haven't ended."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    since = timezone.now() - SIGNUP_GRACE
    rows = (
        EveFleetShipVolunteer.objects.filter(
            character_id__in=EveCharacter.objects.filter(
                user=user
            ).values_list("character_id", flat=True),
            eve_fleet__start_time__gte=since,
        )
        .exclude(eve_fleet__status="cancelled")
        .order_by("eve_fleet__start_time", "character_name")
        .values(
            "eve_fleet_id",
            "character_id",
            "character_name",
            "fitting__name",
            "fitting__ship_id",
            "fleet_fitting__name",
            "fleet_fitting__ship_id",
        )
    )
    return [
        {
            "fleet_id": row["eve_fleet_id"],
            "character_id": row["character_id"],
            "character_name": row["character_name"],
            "fit_name": row["fitting__name"]
            or row["fleet_fitting__name"]
            or "",
            "ship_type_id": row["fitting__ship_id"]
            or row["fleet_fitting__ship_id"],
        }
        for row in rows
    ]
