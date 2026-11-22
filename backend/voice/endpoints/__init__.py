"""Compose the /api/voice router. Import order is route order."""

# pylint: disable=unused-import
from voice.endpoints.base import router
from voice.endpoints import get_login  # noqa: F401
from voice.endpoints import get_status  # noqa: F401
from voice.endpoints import post_connect  # noqa: F401
from voice.endpoints import get_certificates  # noqa: F401
from voice.endpoints import delete_certificate  # noqa: F401
from voice.endpoints import get_fleet_voice  # noqa: F401
from voice.endpoints import post_fleet_co_fc  # noqa: F401
from voice.endpoints import delete_fleet_co_fc  # noqa: F401
from voice.endpoints import post_fleet_wings  # noqa: F401
from voice.endpoints import post_fleet_kick  # noqa: F401
from voice.endpoints import post_ban  # noqa: F401
from voice.endpoints import post_internal_lookup  # noqa: F401
from voice.endpoints import post_internal_redeem  # noqa: F401

__all__ = ["router"]
