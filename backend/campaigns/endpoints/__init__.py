"""Compose the campaigns HTTP API.

Import order is route order: ``/readiness`` has to be registered before
``/{slug}`` or the slug pattern swallows it. The payout-code routes go first
for the same reason.
"""

# pylint: disable=unused-import
from campaigns.endpoints.base import router
from campaigns.endpoints import get_payout_codes  # noqa: F401
from campaigns.endpoints import put_payout_code  # noqa: F401
from campaigns.endpoints import member  # noqa: F401
from campaigns.endpoints import manage  # noqa: F401
from campaigns.endpoints import delete_fitting  # noqa: F401
from campaigns.endpoints import delete_party  # noqa: F401
from campaigns.endpoints import delete_structure  # noqa: F401
from campaigns.endpoints import delete_system  # noqa: F401
from campaigns.endpoints import get_settings  # noqa: F401
from campaigns.endpoints import patch_settings  # noqa: F401
from campaigns.endpoints import post_fitting  # noqa: F401
from campaigns.endpoints import post_order_draft  # noqa: F401
from campaigns.endpoints import post_order_publish  # noqa: F401
from campaigns.endpoints import post_system  # noqa: F401
from campaigns.endpoints import public  # noqa: F401
from campaigns.endpoints import projects  # noqa: F401

__all__ = ["router"]
