"""Seed an active industry order matching the navy-only guide-hull ×100 canvas."""

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
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from industry.test_utils import create_industry_order

# Navy-only kept guide lines (T1 Coercer/Arbitrator/Bellicose/Stabber excluded).
# Ask prices = target_unit_price from the navy-only guide pricing run.
DEFAULT_SELF_ASSIGN_MAXIMUM = 25
KEPT_HULLS = (
    (17619, 8_380_000),  # Caldari Navy Hookbill
    (17841, 8_180_000),  # Federation Navy Comet
    (17703, 8_480_000),  # Imperial Navy Slicer
    (17812, 7_880_000),  # Republic Fleet Firetail
    (37454, 7_880_000),  # Vigil Fleet Issue
    (73789, 19_120_000),  # Coercer Navy Issue
    (73794, 17_320_000),  # Thrasher Fleet Issue
    (73795, 18_820_000),  # Cormorant Navy Issue
    (91858, 17_320_000),  # Talwar Fleet Issue
    (29337, 44_100_000),  # Augoror Navy Issue
    (17709, 44_100_000),  # Omen Navy Issue
    (17634, 43_600_000),  # Caracal Navy Issue
    (29340, 43_600_000),  # Osprey Navy Issue
    (29336, 41_400_000),  # Scythe Fleet Issue
    (17713, 41_400_000),  # Stabber Fleet Issue
)
KEPT_TYPE_IDS = tuple(pair[0] for pair in KEPT_HULLS)


class Command(BaseCommand):
    help = (
        "Seed an active industry order with navy-only guide hulls "
        f"(qty {ORDER_QTY} each, claim max {DEFAULT_SELF_ASSIGN_MAXIMUM}) "
        "for open-orders profit summary demos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantity",
            type=int,
            default=ORDER_QTY,
            help=f"Quantity per hull (default {ORDER_QTY}).",
        )
        parser.add_argument(
            "--self-assign-maximum",
            type=int,
            default=DEFAULT_SELF_ASSIGN_MAXIMUM,
            help=(
                "Per-character claim max for the first 48h "
                f"(default {DEFAULT_SELF_ASSIGN_MAXIMUM})."
            ),
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
            "--replace-all",
            action="store_true",
            help=(
                "Delete ALL local IndustryOrder rows (and cascading items/"
                "assignments) before creating the new order. Local DB only."
            ),
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

        claim_max = int(options["self_assign_maximum"])
        if claim_max < 1:
            raise CommandError("self-assign-maximum must be >= 1")

        if options["replace_all"]:
            # Raw deletes: ORM collector also walks IndustryContractAssociation,
            # which may not be migrated on local DBs yet.
            # pylint: disable=protected-access
            n_assignments = IndustryOrderItemAssignment.objects.count()
            n_items = IndustryOrderItem.objects.count()
            n_orders = IndustryOrder.objects.count()
            for order in IndustryOrder.objects.all():
                order.tribe_groups.clear()
            IndustryOrderItemAssignment.objects.all()._raw_delete(
                using=IndustryOrderItemAssignment.objects.db
            )
            IndustryOrderItem.objects.all()._raw_delete(
                using=IndustryOrderItem.objects.db
            )
            IndustryOrder.objects.all()._raw_delete(
                using=IndustryOrder.objects.db
            )
            # pylint: enable=protected-access
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted local industry data: "
                    f"{n_orders} orders, {n_items} items, "
                    f"{n_assignments} assignments"
                )
            )

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
                self_assign_maximum=claim_max,
                target_unit_price=ask_by_type.get(tid),
            )

        loc_label = location.location_name if location else "(no location)"
        self.stdout.write(
            self.style.SUCCESS(
                f"Created IndustryOrder #{order.pk} "
                f"(code {order.public_short_code}) at {loc_label}: "
                f"{len(type_ids)} hulls ×{qty} (claim max {claim_max})"
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
