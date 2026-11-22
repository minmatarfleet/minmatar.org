"""Completed industry jobs for the homepage week table's Industry tab.

Only finished jobs are shown, at the time they finished: a job that is still
running never appears, so the feed doesn't tell anyone what is being built
right now. A batch of the same blueprint finishing in the same minute is one
line ("built 30 × Rifter").
"""

from __future__ import annotations

from collections import defaultdict

from eveuniverse.models import EveIndustryActivityProduct, EveType

from alliance.helpers.landing_pulse import Event
from eveonline.models import EveCharacterIndustryJob
from market.helpers.pricing import get_history_averages_by_type_id

MANUFACTURING = 1
COPYING = 5
INVENTION = 8
# ESI reports reactions as 9; the SDE's products list them under 11.
REACTIONS = (9, 11)
RESEARCH = (3, 4)
# What a product lookup uses for each job activity.
PRODUCT_ACTIVITY = {MANUFACTURING: 1, INVENTION: 8, 9: 11, 11: 11}
CANCELLED = "cancelled"


def _products(pairs) -> dict[tuple[int, int], tuple[int, int]]:
    """(blueprint, SDE activity) -> (product type, quantity per run)."""
    if not pairs:
        return {}
    blueprints = {bid for bid, _ in pairs}
    out = {}
    for (
        bid,
        aid,
        product,
        quantity,
    ) in EveIndustryActivityProduct.objects.filter(
        eve_type_id__in=blueprints,
        activity_id__in=set(PRODUCT_ACTIVITY.values()),
    ).values_list(
        "eve_type_id", "activity_id", "product_eve_type_id", "quantity"
    ):
        out.setdefault((bid, aid), (product, quantity or 1))
    return out


def _line(activity: int, runs: int, product: tuple[int, int] | None):
    """(verb, quantity of product or 0) for one finished batch."""
    if activity == MANUFACTURING and product:
        quantity = runs * product[1]
        return f"built {quantity:,} ×", quantity
    if activity in REACTIONS and product:
        quantity = runs * product[1]
        return f"reacted {quantity:,} ×", quantity
    if activity in RESEARCH:
        return "researched", 0
    if activity == COPYING:
        return (
            "made 1 copy of" if runs == 1 else f"made {runs:,} copies of"
        ), 0
    if activity == INVENTION:
        return (
            "finished 1 invention run on"
            if runs == 1
            else f"finished {runs:,} invention runs on"
        ), 0
    return "finished a job on", 0


def industry_events(start, end) -> list[Event]:
    """Every industry job that finished in [start, end), one line per pilot,
    blueprint and activity finishing in the same minute."""
    jobs = (
        EveCharacterIndustryJob.objects.filter(
            end_date__gte=start, end_date__lt=end
        )
        .exclude(status=CANCELLED)
        .values_list(
            "character__character_id",
            "activity_id",
            "blueprint_type_id",
            "end_date",
            "runs",
        )
    )
    batches: dict[tuple, dict] = defaultdict(lambda: {"runs": 0, "when": None})
    for character_id, activity, blueprint, ended, runs in jobs:
        key = (
            character_id,
            activity,
            blueprint,
            ended.replace(second=0, microsecond=0),
        )
        batch = batches[key]
        batch["runs"] += runs or 0
        batch["when"] = max(batch["when"] or ended, ended)

    # Each blueprint's own product, plus what it builds (for the icon of a
    # research, copy or invention line).
    products = _products(
        {
            (blueprint, PRODUCT_ACTIVITY[activity])
            for _, activity, blueprint, _ in batches
            if activity in PRODUCT_ACTIVITY
        }
        | {(blueprint, MANUFACTURING) for _, _, blueprint, _ in batches}
    )
    names = dict(
        EveType.objects.filter(
            id__in={b for _, _, b, _ in batches}
            | {p for p, _ in products.values()}
        ).values_list("id", "name")
    )

    lines = []
    for (character_id, activity, blueprint, _), batch in batches.items():
        product = products.get((blueprint, PRODUCT_ACTIVITY.get(activity, 0)))
        verb, quantity = _line(activity, batch["runs"], product)
        if quantity and product:
            subject_id = product[0]
            subject = names.get(subject_id, "an item")
        else:
            # Research, copies and invention name the blueprint; the icon is
            # what it builds, which the image server always has.
            built = products.get((blueprint, MANUFACTURING))
            subject_id = built[0] if built else blueprint
            subject = names.get(blueprint, "a blueprint")
        lines.append(
            (character_id, batch["when"], verb, subject, subject_id, quantity)
        )

    prices = get_history_averages_by_type_id(
        [subject_id for *_, subject_id, quantity in lines if quantity]
    )
    return [
        Event(
            when,
            "industry",
            character_id,
            verb,
            subject,
            "type",
            subject_id,
            amount=round(quantity * float(prices.get(subject_id) or 0)),
        )
        for character_id, when, verb, subject, subject_id, quantity in lines
    ]
