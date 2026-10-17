"""GET /me/gates - what the site may show the signed-in user."""

from typing import List

from django.conf import settings
from ninja import Router, Schema

from authentication import AuthBearer
from groups.helpers.feature_access import get_user_feature_codes
from users.helpers import get_user_permissions

GATE_SOURCES = ("legacy", "shadow", "features")
DEFAULT_GATE_SOURCE = "legacy"

router = Router(tags=["Authentication"])


class LegacyGatesSchema(Schema):
    permissions: List[str]
    is_superuser: bool


class UserGatesSchema(Schema):
    features: List[str]
    legacy: LegacyGatesSchema
    gate_source: str


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
    )
