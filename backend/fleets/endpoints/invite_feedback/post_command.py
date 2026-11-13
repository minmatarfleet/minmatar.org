"""Discord command: preview, remind, or close the feedback round.

The bot calls this with the service token and the Strategic FC's Discord
id. Remind and close do nothing unless confirm is true. The full send is
the production management command.
"""

from app.errors import ErrorResponse
from authentication import AuthBearer, is_service_account
from discord.models import DiscordUser
from fleets.endpoints.invite_feedback.schemas import (
    CommandRequest,
    CommandResponse,
)
from fleets.helpers.invite_feedback import InviteFeedbackError, run_action
from groups.helpers.feature_access import can_use_feature


def post_invite_feedback_command(request, payload: CommandRequest):
    discord_user = (
        DiscordUser.objects.select_related("user")
        .filter(id=payload.discord_user_id)
        .first()
    )
    if discord_user is None:
        return 403, ErrorResponse(
            detail="Link your Discord account on the site first."
        )
    actor = discord_user.user
    if request.user.pk != actor.pk and not is_service_account(request.user):
        return 403, ErrorResponse(detail="Not authorized.")
    if not can_use_feature(actor, "fleets.manage_any"):
        return 403, ErrorResponse(detail="Only Strategic FCs can send this.")
    if payload.action == "send":
        return 400, ErrorResponse(
            detail=("The full send runs from the production command only.")
        )
    try:
        message = run_action(payload.action, confirm=payload.confirm)
    except InviteFeedbackError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return CommandResponse(message=message)


ROUTES = (
    (
        "post",
        "/invite-feedback/command",
        {
            "auth": AuthBearer(),
            "response": {
                200: CommandResponse,
                400: ErrorResponse,
                403: ErrorResponse,
                401: ErrorResponse,
            },
            "description": (
                "Preview, remind, or close the fleet invite feedback round. "
                "Strategic FCs only. The full send is the production "
                "command."
            ),
        },
        post_invite_feedback_command,
    ),
)
