"""The fleet invite feedback form inside Discord.

The DM's Answer button opens a Discord pop-up form. The bot loads the
pilot's form here (to prefill it and to know whether the open-invites
question applies) and saves the answer here, with the service token and the
pilot's Discord id. A pilot may also call these for themselves.
"""

from app.errors import ErrorResponse
from authentication import AuthBearer, is_service_account
from discord.models import DiscordUser
from fleets.endpoints.invite_feedback.schemas import (
    DiscordFormRequest,
    DiscordSubmitRequest,
    FormResponse,
    SubmitError,
)
from fleets.helpers.invite_feedback import (
    SOURCE_DISCORD,
    InviteFeedbackError,
    form_for,
    submit,
)


def _pilot(request, discord_user_id: int):
    discord_user = (
        DiscordUser.objects.select_related("user")
        .filter(id=discord_user_id)
        .first()
    )
    if discord_user is None:
        return None, (
            403,
            ErrorResponse(
                detail="Link your Discord account on the site first."
            ),
        )
    pilot = discord_user.user
    if request.user.pk != pilot.pk and not is_service_account(request.user):
        return None, (403, ErrorResponse(detail="Not authorized."))
    return pilot, None


def post_invite_feedback_discord_form(request, payload: DiscordFormRequest):
    pilot, error = _pilot(request, payload.discord_user_id)
    if error:
        return error
    return 200, FormResponse(**form_for(pilot, edit=True))


def post_invite_feedback_discord_submit(
    request, payload: DiscordSubmitRequest
):
    pilot, error = _pilot(request, payload.discord_user_id)
    if error:
        return error
    answers = payload.model_dump(exclude={"discord_user_id"})
    try:
        panel = submit(pilot, answers, source=SOURCE_DISCORD)
    except InviteFeedbackError as exc:
        return exc.status_code, SubmitError(
            detail=exc.errors[0], errors=exc.errors
        )
    return 200, FormResponse(**panel)


ROUTES = (
    (
        "post",
        "/invite-feedback/discord-form",
        {
            "auth": AuthBearer(),
            "response": {
                200: FormResponse,
                403: ErrorResponse,
                401: ErrorResponse,
            },
            "description": (
                "The fleet invite feedback form for a Discord user (bot). "
                "Always the editable form while the round is open."
            ),
        },
        post_invite_feedback_discord_form,
    ),
    (
        "post",
        "/invite-feedback/discord-submit",
        {
            "auth": AuthBearer(),
            "response": {
                200: FormResponse,
                400: SubmitError,
                403: ErrorResponse,
                401: ErrorResponse,
            },
            "description": (
                "Save a Discord user's fleet invite feedback from the "
                "Discord form (bot). Other's reason is the comment."
            ),
        },
        post_invite_feedback_discord_submit,
    ),
)
