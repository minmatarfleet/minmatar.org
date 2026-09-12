"""Isolated secondary Discord guild seats for tribe groups."""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.utils import timezone

from discord.client import DiscordClient, DiscordError, discord_authorize_url
from discord.helpers import is_discord_unknown_guild_member_error
from discord.models import DiscordUser
from eveonline.helpers.characters import user_primary_character
from tribes.models import (
    TribeExternalGuild,
    TribeExternalGuildSeat,
    TribeGroupMembership,
)

logger = logging.getLogger(__name__)

CLEANUP_FAILURE_ALERT_THRESHOLD = 3
OAUTH_STATE_SALT = "tribes.external_guild.oauth"
OAUTH_STATE_MAX_AGE = 60 * 60 * 24 * 7


def client_for_binding(binding: TribeExternalGuild) -> DiscordClient:
    return DiscordClient.for_guild(binding.guild.guild_id)


def binding_for_group(group_id: int) -> TribeExternalGuild | None:
    return (
        TribeExternalGuild.objects.filter(
            tribe_group_id=group_id, is_active=True
        )
        .select_related("guild", "tribe_group", "tribe_group__tribe")
        .first()
    )


def _snapshot_fields(user: User) -> dict:
    discord_user = DiscordUser.objects.filter(user_id=user.id).first()
    if not discord_user:
        return {}
    primary = user_primary_character(user)
    username = (discord_user.discord_tag or "").split("#", maxsplit=1)[0]
    return {
        "discord_user_id": discord_user.id,
        "discord_username": username or discord_user.discord_tag or "",
        "discord_nickname": discord_user.nickname or "",
        "eve_name": (primary.character_name if primary else "") or "",
    }


def ensure_seat(
    user: User, binding: TribeExternalGuild
) -> TribeExternalGuildSeat | None:
    fields = _snapshot_fields(user)
    if not fields:
        logger.warning(
            "Cannot create external guild seat for user %s: no DiscordUser",
            user.id,
        )
        return None

    seat, created = TribeExternalGuildSeat.objects.get_or_create(
        binding=binding,
        discord_user_id=fields["discord_user_id"],
        defaults={
            "user": user,
            "discord_username": fields["discord_username"],
            "discord_nickname": fields["discord_nickname"],
            "eve_name": fields["eve_name"],
            "status": TribeExternalGuildSeat.STATUS_PENDING_JOIN,
        },
    )
    update_fields = [
        "user",
        "discord_username",
        "discord_nickname",
        "eve_name",
    ]
    seat.user = user
    seat.discord_username = fields["discord_username"]
    seat.discord_nickname = fields["discord_nickname"]
    seat.eve_name = fields["eve_name"]
    if seat.status in (
        TribeExternalGuildSeat.STATUS_REMOVED,
        TribeExternalGuildSeat.STATUS_PENDING_REMOVE,
        TribeExternalGuildSeat.STATUS_CLEANUP_FAILED,
    ):
        seat.status = TribeExternalGuildSeat.STATUS_PENDING_JOIN
        seat.last_error = ""
        seat.failure_count = 0
        update_fields.extend(["status", "last_error", "failure_count"])
    if not created:
        seat.save(update_fields=update_fields + ["updated_at"])
    return seat


def _save_seat(seat: TribeExternalGuildSeat, *fields: str) -> None:
    seat.save(update_fields=[*fields, "updated_at"])


def _mark_present(seat: TribeExternalGuildSeat) -> None:
    seat.status = TribeExternalGuildSeat.STATUS_PRESENT
    seat.last_error = ""
    seat.failure_count = 0
    seat.last_synced_at = timezone.now()
    _save_seat(
        seat,
        "status",
        "last_error",
        "failure_count",
        "last_synced_at",
        "discord_username",
        "discord_nickname",
    )


def _mark_removed(seat: TribeExternalGuildSeat) -> None:
    seat.status = TribeExternalGuildSeat.STATUS_REMOVED
    seat.last_error = ""
    seat.failure_count = 0
    seat.last_synced_at = timezone.now()
    _save_seat(seat, "status", "last_error", "failure_count", "last_synced_at")


def _record_seat_error(
    seat: TribeExternalGuildSeat, error: str, *, alert: bool = False
) -> None:
    seat.last_error = str(error)[:2000]
    seat.failure_count = (seat.failure_count or 0) + 1
    fields = ["last_error", "failure_count"]
    if alert and seat.failure_count >= CLEANUP_FAILURE_ALERT_THRESHOLD:
        seat.status = TribeExternalGuildSeat.STATUS_CLEANUP_FAILED
        fields.append("status")
        _save_seat(seat, *fields)
        _alert_cleanup_failed(seat)
        return
    _save_seat(seat, *fields)


def _refresh_identity(seat: TribeExternalGuildSeat, member: dict) -> None:
    user_payload = member.get("user") if isinstance(member, dict) else None
    if not isinstance(user_payload, dict):
        return
    username = user_payload.get("username")
    if isinstance(username, str) and username:
        seat.discord_username = username
    nick = member.get("nick") or user_payload.get("global_name")
    if isinstance(nick, str) and nick:
        seat.discord_nickname = nick


def _try_oauth_guild_join(
    client: DiscordClient,
    seat: TribeExternalGuildSeat,
    access_token: str,
) -> bool:
    """Join guild via OAuth token. Returns False when the seat was errored."""
    try:
        client.add_guild_member(seat.discord_user_id, access_token)
    except DiscordError as exc:
        if getattr(exc, "status_code", None) != 400:
            _record_seat_error(seat, f"guild_join: {exc}")
            return False
    except requests.RequestException as exc:
        _record_seat_error(seat, f"guild_join: {exc}")
        return False
    return True


def _fetch_member_for_entitled_seat(
    client: DiscordClient,
    seat: TribeExternalGuildSeat,
    *,
    send_dm_if_pending: bool,
) -> dict | None:
    """Return Discord member payload, or None when pending/errored."""
    try:
        return client.get_user(seat.discord_user_id)
    except requests.exceptions.HTTPError as exc:
        if is_discord_unknown_guild_member_error(exc):
            seat.status = TribeExternalGuildSeat.STATUS_PENDING_JOIN
            seat.last_error = ""
            _save_seat(seat, "status", "last_error")
            if send_dm_if_pending:
                send_pending_join_dm(seat)
            return None
        _record_seat_error(seat, f"get_member: {exc}")
        return None
    except (DiscordError, requests.RequestException, RuntimeError) as exc:
        _record_seat_error(seat, f"get_member: {exc}")
        return None


def apply_seat(
    seat: TribeExternalGuildSeat,
    *,
    entitled: bool,
    access_token: str | None = None,
    send_dm_if_pending: bool = False,
) -> str:
    """
    Bring a seat to the desired Discord state.

    Returns the resulting seat status.
    """
    client = client_for_binding(seat.binding)
    if not entitled:
        return _apply_remove(seat, client)

    if access_token and not _try_oauth_guild_join(client, seat, access_token):
        return seat.status

    member = _fetch_member_for_entitled_seat(
        client, seat, send_dm_if_pending=send_dm_if_pending
    )
    if member is None:
        return seat.status

    _refresh_identity(seat, member)
    try:
        client.add_user_role(seat.discord_user_id, seat.binding.member_role_id)
    except (DiscordError, requests.RequestException, RuntimeError) as exc:
        _record_seat_error(seat, f"add_role: {exc}")
        return seat.status

    _mark_present(seat)
    return seat.status


def _apply_remove(seat: TribeExternalGuildSeat, client: DiscordClient) -> str:
    if seat.status == TribeExternalGuildSeat.STATUS_REMOVED:
        return seat.status
    seat.status = TribeExternalGuildSeat.STATUS_PENDING_REMOVE
    _save_seat(seat, "status")
    try:
        client.kick_guild_member(seat.discord_user_id)
    except requests.exceptions.HTTPError as exc:
        if is_discord_unknown_guild_member_error(exc):
            _mark_removed(seat)
            return seat.status
        _record_seat_error(seat, f"kick: {exc}", alert=True)
        return seat.status
    except (DiscordError, requests.RequestException, RuntimeError) as exc:
        _record_seat_error(seat, f"kick: {exc}", alert=True)
        return seat.status
    _mark_removed(seat)
    return seat.status


def on_membership_became_active(membership: TribeGroupMembership) -> None:
    binding = binding_for_group(membership.tribe_group_id)
    if binding is None:
        return
    seat = ensure_seat(membership.user, binding)
    if seat is None:
        return
    apply_seat(seat, entitled=True, send_dm_if_pending=True)


def on_membership_became_inactive(membership: TribeGroupMembership) -> None:
    binding = binding_for_group(membership.tribe_group_id)
    if binding is None:
        return
    still_active = TribeGroupMembership.objects.filter(
        user=membership.user,
        tribe_group_id=membership.tribe_group_id,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()
    if still_active:
        return
    seat = (
        TribeExternalGuildSeat.objects.filter(
            binding=binding, user=membership.user
        )
        .exclude(status=TribeExternalGuildSeat.STATUS_REMOVED)
        .first()
    )
    if seat is None:
        fields = _snapshot_fields(membership.user)
        if not fields:
            return
        seat = TribeExternalGuildSeat.objects.filter(
            binding=binding,
            discord_user_id=fields["discord_user_id"],
        ).first()
        if seat is None:
            return
    apply_seat(seat, entitled=False)


def prepare_seats_for_user_delete(user: User) -> None:
    seats = list(
        TribeExternalGuildSeat.objects.filter(user=user)
        .exclude(status=TribeExternalGuildSeat.STATUS_REMOVED)
        .select_related("binding__guild", "binding__tribe_group")
    )
    if not seats:
        return
    fields = _snapshot_fields(user)
    for seat in seats:
        if fields:
            seat.discord_username = fields.get(
                "discord_username", seat.discord_username
            )
            seat.discord_nickname = fields.get(
                "discord_nickname", seat.discord_nickname
            )
            seat.eve_name = (
                fields.get("eve_name", seat.eve_name) or seat.eve_name
            )
        seat.user = None
        _save_seat(
            seat,
            "user",
            "discord_username",
            "discord_nickname",
            "eve_name",
        )
        apply_seat(seat, entitled=False)


def seat_for_user_group(
    user: User, group_id: int
) -> TribeExternalGuildSeat | None:
    binding = binding_for_group(group_id)
    if binding is None:
        return None
    return (
        TribeExternalGuildSeat.objects.filter(binding=binding, user=user)
        .exclude(status=TribeExternalGuildSeat.STATUS_REMOVED)
        .first()
    )


def allowlisted_redirect_url(url: str) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    if not url:
        return base
    parts = urlsplit(url)
    base_parts = urlsplit(base)
    if parts.scheme and parts.netloc and parts.netloc != base_parts.netloc:
        return base
    if not parts.scheme:
        return urlunsplit(
            (
                base_parts.scheme,
                base_parts.netloc,
                parts.path or "/",
                parts.query,
                parts.fragment,
            )
        )
    return url


def encode_oauth_state(
    *, group_id: int, user_id: int, redirect_url: str
) -> str:
    return signing.dumps(
        {
            "group_id": group_id,
            "user_id": user_id,
            "redirect_url": allowlisted_redirect_url(redirect_url),
        },
        salt=OAUTH_STATE_SALT,
    )


def decode_oauth_state(state: str) -> dict | None:
    try:
        payload = signing.loads(
            state, salt=OAUTH_STATE_SALT, max_age=OAUTH_STATE_MAX_AGE
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    if "group_id" not in payload or "user_id" not in payload:
        return None
    payload["redirect_url"] = allowlisted_redirect_url(
        payload.get("redirect_url") or ""
    )
    return payload


def pending_join_return_url(seat: TribeExternalGuildSeat) -> str:
    base = getattr(settings, "WEB_LINK_URL", "https://my.minmatar.org").rstrip(
        "/"
    )
    group = seat.binding.tribe_group
    return f"{base}/alliance/tribes/{group.tribe_id}/{group.id}/"


def pending_join_oauth_url(seat: TribeExternalGuildSeat) -> str | None:
    redirect_uri = getattr(settings, "DISCORD_EXTERNAL_GUILD_REDIRECT_URL", "")
    if not redirect_uri or seat.user_id is None:
        return None
    state = encode_oauth_state(
        group_id=seat.binding.tribe_group_id,
        user_id=seat.user_id,
        redirect_url=pending_join_return_url(seat),
    )
    return discord_authorize_url(
        settings.DISCORD_CLIENT_ID, redirect_uri, state=state
    )


def build_pending_join_dm_message(seat: TribeExternalGuildSeat) -> str:
    guild_name = seat.binding.guild.name
    group_name = seat.binding.tribe_group.name
    join_url = pending_join_oauth_url(seat)
    if not join_url:
        base = getattr(
            settings, "WEB_LINK_URL", "https://my.minmatar.org"
        ).rstrip("/")
        join_url = (
            f"{base}/redirects/external_guild_join"
            f"?group_id={seat.binding.tribe_group_id}"
        )
    return (
        f"**Welcome to {group_name}**\n"
        f"Ops run on the **{guild_name}** Discord "
        f"(separate from Minmatar Fleet).\n"
        f"Click to authorize Discord and join:\n{join_url}"
    )


def send_pending_join_dm(seat: TribeExternalGuildSeat) -> bool:
    try:
        DiscordClient().send_dm(
            str(seat.discord_user_id),
            message=build_pending_join_dm_message(seat),
        )
        return True
    except (DiscordError, requests.RequestException, RuntimeError) as exc:
        logger.warning(
            "Failed pending-join DM for seat %s (discord %s): %s",
            seat.pk,
            seat.discord_user_id,
            exc,
        )
        return False


def join_seat_with_oauth_token(
    seat: TribeExternalGuildSeat, access_token: str
) -> bool:
    return (
        apply_seat(seat, entitled=True, access_token=access_token)
        == TribeExternalGuildSeat.STATUS_PRESENT
    )


def reconcile_external_guilds() -> dict:
    stats = {
        "bindings": 0,
        "joined": 0,
        "kicked": 0,
        "alerts": 0,
        "errors": 0,
    }
    bindings = TribeExternalGuild.objects.filter(
        is_active=True
    ).select_related("guild", "tribe_group")
    for binding in bindings:
        stats["bindings"] += 1
        try:
            result = _reconcile_binding(binding)
            for key, value in result.items():
                stats[key] = stats.get(key, 0) + value
        except Exception as exc:  # pylint: disable=broad-except
            stats["errors"] += 1
            logger.exception(
                "External guild reconcile failed for binding %s: %s",
                binding.pk,
                exc,
            )
    return stats


def _reconcile_seats(
    binding: TribeExternalGuild, active_user_ids: set[int]
) -> tuple[dict, set[int]]:
    result = {"joined": 0, "kicked": 0, "alerts": 0}
    seats = list(
        TribeExternalGuildSeat.objects.filter(binding=binding).exclude(
            status=TribeExternalGuildSeat.STATUS_REMOVED
        )
    )
    for seat in seats:
        entitled = seat.user_id is not None and seat.user_id in active_user_ids
        before = seat.status
        status = apply_seat(seat, entitled=entitled)
        if entitled and status == TribeExternalGuildSeat.STATUS_PRESENT:
            if before != TribeExternalGuildSeat.STATUS_PRESENT:
                result["joined"] += 1
        elif not entitled and status == TribeExternalGuildSeat.STATUS_REMOVED:
            result["kicked"] += 1
        elif status == TribeExternalGuildSeat.STATUS_CLEANUP_FAILED:
            result["alerts"] += 1
    return result, {seat.discord_user_id for seat in seats}


def _kick_stray_role_holders(
    client: DiscordClient,
    binding: TribeExternalGuild,
    members_by_id: dict[int, dict],
    seat_discord_ids: set[int],
) -> dict:
    result = {"kicked": 0, "errors": 0}
    role_id = str(binding.member_role_id)
    for member_id, member in members_by_id.items():
        roles = [str(r) for r in member.get("roles", [])]
        if role_id not in roles or member_id in seat_discord_ids:
            continue
        if member.get("user", {}).get("bot"):
            continue
        try:
            client.kick_guild_member(member_id)
            result["kicked"] += 1
            logger.info(
                "Kicked stray external-guild role holder %s from guild %s",
                member_id,
                binding.guild.guild_id,
            )
        except requests.exceptions.HTTPError as exc:
            if is_discord_unknown_guild_member_error(exc):
                continue
            result["errors"] += 1
        except (DiscordError, requests.RequestException):
            result["errors"] += 1
    return result


def _reconcile_binding(binding: TribeExternalGuild) -> dict:
    result = {"joined": 0, "kicked": 0, "alerts": 0, "errors": 0}
    client = client_for_binding(binding)
    try:
        members = client.get_members()
    except (DiscordError, requests.RequestException) as exc:
        logger.error(
            "Failed listing members for external guild %s: %s",
            binding.guild.guild_id,
            exc,
        )
        result["errors"] += 1
        return result

    members_by_id = {int(m["user"]["id"]): m for m in members if m.get("user")}
    active_user_ids = set(
        TribeGroupMembership.objects.filter(
            tribe_group_id=binding.tribe_group_id,
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).values_list("user_id", flat=True)
    )
    seat_stats, seat_discord_ids = _reconcile_seats(binding, active_user_ids)
    for key, value in seat_stats.items():
        result[key] += value
    stray_stats = _kick_stray_role_holders(
        client, binding, members_by_id, seat_discord_ids
    )
    for key, value in stray_stats.items():
        result[key] += value
    return result


def _alert_cleanup_failed(seat: TribeExternalGuildSeat) -> None:
    binding = seat.binding
    message = (
        f"**External Discord cleanup failed** for **{binding.tribe_group}**\n"
        f"- Discord: `{seat.discord_username}` (`{seat.discord_user_id}`)\n"
        f"- Nickname: `{seat.discord_nickname or '—'}`\n"
        f"- EVE: `{seat.eve_name or '—'}`\n"
        f"- Error: `{seat.last_error[:500]}`"
    )
    client = DiscordClient()
    if binding.alert_channel_id:
        try:
            client.create_message(binding.alert_channel_id, message=message)
            return
        except (DiscordError, requests.RequestException) as exc:
            logger.warning(
                "Failed alert channel post for seat %s: %s", seat.pk, exc
            )
    chief = binding.tribe_group.chief or binding.tribe_group.tribe.chief
    if chief is not None:
        chief_discord = DiscordUser.objects.filter(user_id=chief.id).first()
        if chief_discord is not None:
            try:
                client.send_dm(str(chief_discord.id), message=message)
            except (DiscordError, requests.RequestException) as exc:
                logger.warning("Failed chief DM for seat %s: %s", seat.pk, exc)


def append_query(base_url: str, **params: str) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )
