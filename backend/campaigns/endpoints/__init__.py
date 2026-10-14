"""Compose the campaigns HTTP API.

Import order is route order: ``/readiness`` has to be registered before
``/{slug}`` or the slug pattern swallows it.
"""

from campaigns.endpoints.base import router
from campaigns.endpoints import member  # noqa: F401  (registers routes)
from campaigns.endpoints import manage  # noqa: F401
from campaigns.endpoints import public  # noqa: F401

__all__ = ["router"]
