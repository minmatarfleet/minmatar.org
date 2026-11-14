"""Private (invite-only) fleets and ship targets.
See docs/fleets/private-fleets.md."""

from fleets.endpoints.private.answers import ROUTES as answer_routes
from fleets.endpoints.private.declassify import ROUTES as declassify_routes
from fleets.endpoints.private.invites import ROUTES as invite_routes
from fleets.endpoints.private.rsvp import ROUTES as rsvp_routes
from fleets.endpoints.private.targets import ROUTES as target_routes

_ROUTES = (
    invite_routes
    + answer_routes
    + rsvp_routes
    + target_routes
    + declassify_routes
)

__all__ = ["_ROUTES"]
