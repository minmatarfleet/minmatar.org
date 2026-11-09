"""GET /me/gates - what the site may show the signed-in user."""

from typing import List

from django.conf import settings
from ninja import Router, Schema

from authentication import AuthBearer
from eveonline.constants import HOLDING_CORPORATION_TICKER
from eveonline.helpers.alliances import member_corporations
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.models import EvePlayer
from groups.helpers.feature_access import get_user_feature_codes
from users.helpers import get_user_permissions

GATE_SOURCES = ("legacy", "shadow", "features")
DEFAULT_GATE_SOURCE = "legacy"

router = Router(tags=["Authentication"])


class LegacyGatesSchema(Schema):
    permissions: List[str]
    is_superuser: bool


class LedCorporationSchema(Schema):
    corporation_id: int
    name: str


class UserGatesSchema(Schema):
    features: List[str]
    legacy: LegacyGatesSchema
    gate_source: str
    # Corporations the user is CEO or a director of (not the holding
    # corporation). The main character's corporation comes first when they
    # lead it, then other CEO corporations, then director corporations by
    # name. Navigation links to the first.
    led_corporations: List[LedCorporationSchema] = []


def frontend_gate_source() -> str:
    """Which answer the frontend acts on: legacy, shadow, or features."""
    value = getattr(settings, "FRONTEND_GATE_SOURCE", DEFAULT_GATE_SOURCE)
    return value if value in GATE_SOURCES else DEFAULT_GATE_SOURCE


@router.get(
    "/me/gates",
    summary="Get the features and legacy permissions the site gates on",
    description=(
        "features: every pilot feature code the user may use, evaluated "
        "without a resource. legacy: the permission strings and superuser "
        "flag the site gated on before features. gate_source: which of the "
        "two the site should act on."
    ),
    auth=AuthBearer(),
    response={200: UserGatesSchema},
)
def get_me_gates(request):
    user = request.user
    return UserGatesSchema(
        features=get_user_feature_codes(user),
        legacy=LegacyGatesSchema(
            permissions=sorted(get_user_permissions(user.id)),
            is_superuser=user.is_superuser,
        ),
        gate_source=frontend_gate_source(),
        led_corporations=led_corporations(user.id),
    )


def led_corporations(user_id: int) -> list[LedCorporationSchema]:
    corporations = member_corporations().exclude(
        ticker=HOLDING_CORPORATION_TICKER
    )
    ceo_of = set(
        corporations.filter(owned_by_q(user_id, "ceo__")).values_list(
            "corporation_id", flat=True
        )
    )
    rows = (
        corporations.filter(
            owned_by_q(user_id, "ceo__") | owned_by_q(user_id, "directors__")
        )
        .values_list("corporation_id", "name")
        .distinct()
    )
    primary_corporation_id = (
        EvePlayer.objects.filter(user_id=user_id)
        .values_list("primary_character__corporation_id", flat=True)
        .first()
    )
    return [
        LedCorporationSchema(corporation_id=corporation_id, name=name)
        for corporation_id, name in sorted(
            rows,
            key=lambda row: (
                row[0] != primary_corporation_id,
                row[0] not in ceo_of,
                row[1],
            ),
        )
    ]
