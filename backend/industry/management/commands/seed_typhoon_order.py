"""Create a demo IndustryOrder with 40 Typhoons for planner testing."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveCharacter, EveLocation
from industry.models import IndustryOrderItem
from industry.test_utils import create_industry_order

TYPHOON_TYPE_ID = 644


class Command(BaseCommand):
    help = "Seed an active industry order for 40 Typhoons (planner demo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantity",
            type=int,
            default=40,
            help="Typhoon quantity (default 40).",
        )
        parser.add_argument(
            "--character-id",
            type=int,
            default=None,
            help="Eve character_id for the order owner (default: first character).",
        )

    def handle(self, *args, **options):
        qty = options["quantity"]
        if qty < 1:
            raise CommandError("quantity must be >= 1")

        typhoon = EveType.objects.filter(id=TYPHOON_TYPE_ID).first()
        if typhoon is None:
            raise CommandError(
                f"EveType {TYPHOON_TYPE_ID} (Typhoon) not found. "
                "Load SDE / EveType data first."
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

        location = EveLocation.objects.order_by("location_id").first()

        order = create_industry_order(
            needed_by=timezone.now().date() + timedelta(days=30),
            character=character,
            location=location,
            contract_to=character.character_name,
        )
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=typhoon,
            quantity=qty,
            self_assign_maximum=qty,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created IndustryOrder #{order.pk} "
                f"(code {order.public_short_code}): "
                f"{typhoon.name} x{qty} (item #{item.pk})"
            )
        )
        self.stdout.write(
            f"Open: /industry/orders/  then expand the order, or "
            f"/industry/orders/planner?order_id={order.pk}&item_id={item.pk}"
        )
        self.stdout.write(f"API: GET /api/industry/orders/{order.pk}")
