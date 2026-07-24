"""Seed an active industry order matching the guide-hull ×100 canvas."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveCharacter, EveLocation
from industry.helpers.guide_order_summary_export import (
    GUIDE_HULL_CANDIDATES,
    MIN_ORDER_PROFIT_ISK,
    ORDER_QTY,
    EXPLICIT_CUT_TYPE_IDS,
)
from industry.models import IndustryOrderItem
from industry.test_utils import create_industry_order

# Kept guide lines (same set as frontend guide-order-summary.ts).
# Ask prices match the canvas Jita sells used when the guide report was baked.
KEPT_HULLS = (
    (17619, 8_000_000),  # Caldari Navy Hookbill
    (17841, 8_465_000),  # Federation Navy Comet
    (17703, 10_000_000),  # Imperial Navy Slicer
    (17812, 8_998_000),  # Republic Fleet Firetail
    (37454, 11_490_000),  # Vigil Fleet Issue
    (73789, 21_300_000),  # Coercer Navy Issue
    (73794, 18_840_000),  # Thrasher Fleet Issue
    (73795, 18_000_000),  # Cormorant Navy Issue
    (91858, 19_522_645),  # Talwar Fleet Issue
    (16236, 1_386_000),  # Coercer
    (628, 9_198_000),  # Arbitrator
    (29337, 43_560_000),  # Augoror Navy Issue
    (17709, 44_230_000),  # Omen Navy Issue
    (17634, 40_000_000),  # Caracal Navy Issue
    (29340, 40_930_000),  # Osprey Navy Issue
    (630, 11_790_000),  # Bellicose
    (29336, 42_840_000),  # Scythe Fleet Issue
    (622, 11_620_000),  # Stabber
    (17713, 43_340_000),  # Stabber Fleet Issue
)
KEPT_TYPE_IDS = tuple(pair[0] for pair in KEPT_HULLS)


class Command(BaseCommand):
    help = (
        "Seed an active industry order with the kept guide hulls "
        f"(qty {ORDER_QTY} each) for open-orders profit summary demos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantity",
            type=int,
            default=ORDER_QTY,
            help=f"Quantity per hull (default {ORDER_QTY}).",
        )
        parser.add_argument(
            "--character-id",
            type=int,
            default=None,
            help="Eve character_id for the order owner (default: first character).",
        )
        parser.add_argument(
            "--location-id",
            type=int,
            default=None,
            help="EveLocation.location_id (default: Amamake if present).",
        )
        parser.add_argument(
            "--include-cuts",
            action="store_true",
            help=(
                "Include the full guide catalog except explicit cuts "
                f"(still drops under-{MIN_ORDER_PROFIT_ISK // 1_000_000}M lines "
                "only if you filter elsewhere; here adds all non-explicit candidates)."
            ),
        )

    def handle(self, *args, **options):
        qty = int(options["quantity"])
        if qty < 1:
            raise CommandError("quantity must be >= 1")

        if options["include_cuts"]:
            type_ids = [
                int(c["type_id"])
                for c in GUIDE_HULL_CANDIDATES
                if int(c["type_id"]) not in EXPLICIT_CUT_TYPE_IDS
            ]
            ask_by_type = {tid: None for tid in type_ids}
        else:
            type_ids = [pair[0] for pair in KEPT_HULLS]
            ask_by_type = dict(KEPT_HULLS)

        types = {
            tid: EveType.objects.filter(id=tid).first() for tid in type_ids
        }
        missing = [tid for tid, et in types.items() if et is None]
        if missing:
            raise CommandError(
                f"Missing EveType rows: {missing}. Load SDE first."
            )

        character_id = options["character_id"]
        if character_id is not None:
            character = EveCharacter.objects.filter(
                character_id=character_id
            ).first()
            if character is None:
                raise CommandError(
                    f"No EveCharacter with character_id={character_id}"
                )
        else:
            character = EveCharacter.objects.order_by("id").first()
            if character is None:
                raise CommandError(
                    "No EveCharacter in DB. Create one or pass --character-id."
                )

        location_id = options["location_id"]
        if location_id is not None:
            location = EveLocation.objects.filter(
                location_id=location_id
            ).first()
            if location is None:
                raise CommandError(
                    f"No EveLocation with location_id={location_id}"
                )
        else:
            location = (
                EveLocation.objects.filter(
                    location_name__icontains="Amamake"
                ).first()
                or EveLocation.objects.order_by("location_id").first()
            )

        order = create_industry_order(
            needed_by=timezone.now().date() + timedelta(days=30),
            character=character,
            location=location,
            contract_to=character.character_name,
        )
        for tid in type_ids:
            IndustryOrderItem.objects.create(
                order=order,
                eve_type=types[tid],
                quantity=qty,
                self_assign_maximum=qty,
                target_unit_price=ask_by_type.get(tid),
            )

        loc_label = location.location_name if location else "(no location)"
        self.stdout.write(
            self.style.SUCCESS(
                f"Created IndustryOrder #{order.pk} "
                f"(code {order.public_short_code}) at {loc_label}: "
                f"{len(type_ids)} hulls ×{qty}"
            )
        )
        self.stdout.write(
            "Open: /industry/orders/summary/ "
            f"(include order #{order.pk} / {order.public_short_code})"
        )
        self.stdout.write(f"API: GET /api/industry/orders/{order.pk}")
        self.stdout.write(
            "API: GET /api/industry/orders/profit-summary"
            f"?order_ids={order.pk}&open_only=true"
        )
