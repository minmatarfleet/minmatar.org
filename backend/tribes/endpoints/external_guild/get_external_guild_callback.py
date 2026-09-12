"""GET "/external-guild/callback" — OAuth callback for external guild join."""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from ninja import Router

from app.errors import create_error_id
from discord.client import DiscordClient, DiscordError
from discord.models import DiscordUser
from tribes.helpers.external_guild import (
    append_query,
    decode_oauth_state,
    join_seat_with_oauth_token,
)
from tribes.models import TribeExternalGuildSeat

logger = logging.getLogger(__name__)
discord = DiscordClient()

PATH = "/external-guild/callback"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Discord OAuth callback for tribe external guild join.",
    "response": {302: None},
    "include_in_schema": False,
}

router = Router(tags=["Tribes - External Guild"])


def get_external_guild_callback(
    request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
):
    payload = decode_oauth_state(state or "")
    redirect_url = (
        payload["redirect_url"]
        if payload
        else getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org")
    )

    if error or not code or payload is None:
        error_id = create_error_id()
        logger.info(
            "External guild OAuth denied/invalid: error=%s state=%s (%s)",
            error,
            bool(state),
            error_id,
        )
        return redirect(
            append_query(redirect_url, external_guild="denied", id=error_id)
        )

    redirect_uri = getattr(settings, "DISCORD_EXTERNAL_GUILD_REDIRECT_URL", "")
    if not redirect_uri:
        return redirect(
            append_query(redirect_url, external_guild="misconfigured")
        )

    try:
        profile, access_token = discord.exchange_code(code, redirect_uri)
    except DiscordError as exc:
        logger.error(
            "External guild OAuth exchange failed (%s): %s",
            exc.id,
            exc.description,
        )
        return redirect(
            append_query(
                redirect_url,
                external_guild="exchange_failed",
                id=exc.id,
            )
        )

    discord_id = int(profile["id"])
    user = User.objects.filter(pk=payload["user_id"]).first()
    if user is None:
        return redirect(append_query(redirect_url, external_guild="no_user"))

    linked = DiscordUser.objects.filter(user_id=user.id).first()
    if linked is None or linked.id != discord_id:
        return redirect(
            append_query(redirect_url, external_guild="discord_mismatch")
        )

    seat = (
        TribeExternalGuildSeat.objects.filter(
            binding__tribe_group_id=int(payload["group_id"]),
            user=user,
        )
        .exclude(status=TribeExternalGuildSeat.STATUS_REMOVED)
        .select_related("binding__guild")
        .first()
    )
    if seat is None:
        return redirect(append_query(redirect_url, external_guild="no_seat"))

    if join_seat_with_oauth_token(seat, access_token):
        return redirect(append_query(redirect_url, external_guild="joined"))
    return redirect(append_query(redirect_url, external_guild="join_failed"))


router.get(PATH, **ROUTE_SPEC)(get_external_guild_callback)
