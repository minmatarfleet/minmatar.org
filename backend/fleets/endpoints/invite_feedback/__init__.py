"""Fleet invite feedback routes. See docs/fleets/private-fleets.md."""

from fleets.endpoints.invite_feedback.get_form import ROUTES as form_routes
from fleets.endpoints.invite_feedback.post_discord import (
    ROUTES as discord_routes,
)
from fleets.endpoints.invite_feedback.get_results import (
    ROUTES as result_routes,
)
from fleets.endpoints.invite_feedback.post_command import (
    ROUTES as command_routes,
)
from fleets.endpoints.invite_feedback.post_form import ROUTES as submit_routes

_ROUTES = (
    result_routes
    + command_routes
    + discord_routes
    + form_routes
    + submit_routes
)

__all__ = ["_ROUTES"]
