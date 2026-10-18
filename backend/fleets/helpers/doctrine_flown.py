"""
Which doctrine a fleet actually flew, read from the hulls its pilots were in.

A doctrine matches when at least half the pilots (capsules left out) are in
a hull one of its fittings uses. The doctrine with the most such pilots
wins; ties go to the fleet's planned doctrine, then by name. Only hulls are
known, not fits, so two doctrines on the same hulls match equally.
"""

from collections import Counter

from fittings.models import EveDoctrineFitting

HULLS_SHOWN = 4


def doctrine_hulls() -> dict[int, dict]:
    """Every doctrine's name and hull ids, in one query."""
    doctrines: dict[int, dict] = {}
    for doctrine_id, name, ship_id in EveDoctrineFitting.objects.values_list(
        "doctrine_id", "doctrine__name", "fitting__ship_id"
    ):
        doctrine = doctrines.setdefault(
            doctrine_id, {"name": name, "hulls": set()}
        )
        doctrine["hulls"].add(ship_id)
    return doctrines


def pick_doctrine(
    hulls: dict[int, tuple[int, str]],
    doctrines: dict[int, dict],
    preferred_id: int | None = None,
) -> int | None:
    """
    The doctrine flown by these pilots, from ``{character_id: (ship_type_id,
    ship_name)}`` with capsules already left out; None when none reaches
    half the pilots.
    """
    ranked = []
    for doctrine_id, doctrine in doctrines.items():
        flying = _flying(hulls, doctrine)
        if flying and flying * 2 >= len(hulls):
            ranked.append(
                (
                    -flying,
                    doctrine_id != preferred_id,
                    doctrine["name"],
                    doctrine_id,
                )
            )
    return min(ranked)[3] if ranked else None


def _flying(hulls: dict[int, tuple[int, str]], doctrine: dict) -> int:
    return sum(
        1 for type_id, _ in hulls.values() if type_id in doctrine["hulls"]
    )


def doctrine_segment(
    hulls: dict[int, tuple[int, str]],
    doctrines: dict[int, dict],
    doctrine_id: int | None,
) -> dict:
    """
    Share, pilot count and top hulls for one stretch of the fleet.

    ``share`` is the percentage of pilots in the doctrine's hulls, 0 when
    ``doctrine_id`` is None.
    """
    pilots = len(hulls)
    doctrine = doctrines.get(doctrine_id) if doctrine_id else None
    counts = Counter(type_id for type_id, _ in hulls.values())
    names = dict(hulls.values())
    top = sorted(counts.items(), key=lambda kv: (-kv[1], names[kv[0]]))
    return {
        "doctrine_id": doctrine_id if doctrine else None,
        "doctrine_name": doctrine["name"] if doctrine else None,
        "share": (
            round(100 * _flying(hulls, doctrine) / pilots)
            if doctrine and pilots
            else 0
        ),
        "pilots": pilots,
        "hulls": [
            {"ship_type_id": type_id, "ship_name": names[type_id], "count": n}
            for type_id, n in top[:HULLS_SHOWN]
        ],
    }
