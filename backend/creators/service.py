"""Business logic for creator account linking and media ingest."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from creators.clients.reddit import (
    list_user_submitted,
    normalize_reddit_username,
)
from creators.clients.twitch import TwitchClient
from creators.clients.youtube import YouTubeClient
from creators.models import (
    CreatorAccount,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from creators.oauth import (
    OAuthError,
    TokenPayload,
    exchange_code,
    refresh_access_token,
    revoke_token,
    twitch_app_access_token,
)

logger = logging.getLogger(__name__)


def upsert_account_from_oauth(
    user: User, provider: str, code: str
) -> CreatorAccount:
    token = exchange_code(provider, code)
    identity = _fetch_identity(provider, token.access_token)
    return _upsert_account(user, provider, token, identity)


def _fetch_identity(provider: str, access_token: str) -> dict[str, Any]:
    if provider == CreatorProvider.TWITCH:
        users = TwitchClient(access_token).get_users()
        if not users:
            raise OAuthError("identity_failed", "Twitch user lookup failed")
        user = users[0]
        return {
            "platform_user_id": str(user["id"]),
            "platform_username": user.get("login")
            or user.get("display_name")
            or "",
            "extra": {
                "display_name": user.get("display_name") or "",
                "profile_image_url": user.get("profile_image_url") or "",
            },
        }

    if provider == CreatorProvider.YOUTUBE:
        channel = YouTubeClient(access_token).get_my_channel()
        if not channel:
            raise OAuthError(
                "identity_failed", "YouTube channel lookup failed"
            )
        snippet = channel.get("snippet") or {}
        content = channel.get("contentDetails") or {}
        related = content.get("relatedPlaylists") or {}
        return {
            "platform_user_id": str(channel["id"]),
            "platform_username": snippet.get("title") or "",
            "extra": {
                "uploads_playlist_id": related.get("uploads") or "",
                "thumbnail_url": (
                    (snippet.get("thumbnails") or {})
                    .get("default", {})
                    .get("url")
                    or ""
                ),
            },
        }

    raise OAuthError("unknown_provider", f"Unknown provider: {provider}")


@transaction.atomic
def _upsert_account(
    user: User,
    provider: str,
    token: TokenPayload,
    identity: dict[str, Any],
) -> CreatorAccount:
    platform_user_id = identity["platform_user_id"]
    if not platform_user_id:
        raise OAuthError("identity_failed", "Missing platform user id")

    # Drop any other user holding this platform identity.
    CreatorAccount.objects.filter(
        provider=provider, platform_user_id=platform_user_id
    ).exclude(user=user).delete()

    account, _ = CreatorAccount.objects.update_or_create(
        user=user,
        provider=provider,
        defaults={
            "platform_user_id": platform_user_id,
            "platform_username": identity.get("platform_username") or "",
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_expires_at": token.expires_at,
            "scopes": token.scopes,
            "extra": identity.get("extra") or {},
            "token_invalid": False,
        },
    )
    return account


def ensure_valid_access_token(account: CreatorAccount) -> str | None:
    """Refresh if expired; return access token or None if invalid."""
    if account.token_invalid:
        return None

    expires = account.token_expires_at
    needs_refresh = False
    if expires is not None:
        needs_refresh = expires <= timezone.now() + timedelta(minutes=2)
    elif not account.access_token and account.refresh_token:
        needs_refresh = True

    if not needs_refresh and account.access_token:
        return account.access_token

    if not account.refresh_token:
        account.token_invalid = True
        account.save(update_fields=["token_invalid", "updated_at"])
        return None

    try:
        payload = refresh_access_token(account.provider, account.refresh_token)
    except OAuthError:
        logger.warning(
            "Refresh failed for creator account %s (%s)",
            account.id,
            account.provider,
        )
        account.token_invalid = True
        account.save(update_fields=["token_invalid", "updated_at"])
        return None

    account.access_token = payload.access_token
    if payload.refresh_token:
        account.refresh_token = payload.refresh_token
    account.token_expires_at = payload.expires_at
    account.scopes = payload.scopes or account.scopes
    account.token_invalid = False
    account.save(
        update_fields=[
            "access_token",
            "refresh_token",
            "token_expires_at",
            "scopes",
            "token_invalid",
            "updated_at",
        ]
    )
    return account.access_token


def disconnect_account(user: User, provider: str) -> bool:
    account = CreatorAccount.objects.filter(
        user=user, provider=provider
    ).first()
    if not account:
        return False
    if provider != CreatorProvider.REDDIT:
        revoke_token(provider, account.refresh_token or account.access_token)
    account.delete()
    return True


def link_reddit_username(user: User, username: str) -> CreatorAccount:
    """Store a Reddit username for public-post polling (no user OAuth)."""
    name = normalize_reddit_username(username)
    if not name:
        raise ValueError("username_required")

    # Case-insensitive uniqueness across users.
    platform_user_id = name.lower()
    CreatorAccount.objects.filter(
        provider=CreatorProvider.REDDIT, platform_user_id=platform_user_id
    ).exclude(user=user).delete()

    account, _ = CreatorAccount.objects.update_or_create(
        user=user,
        provider=CreatorProvider.REDDIT,
        defaults={
            "platform_user_id": platform_user_id,
            "platform_username": name,
            "access_token": "",
            "refresh_token": "",
            "token_expires_at": None,
            "scopes": [],
            "extra": {},
            "token_invalid": False,
        },
    )
    return account


def poll_twitch_live() -> int:
    """Update is_live flags for all Twitch accounts. Returns accounts updated."""
    accounts = list(
        CreatorAccount.objects.filter(provider=CreatorProvider.TWITCH)
    )
    if not accounts:
        return 0

    app_token = twitch_app_access_token()
    if not app_token:
        logger.warning("Skipping Twitch live poll: no app token")
        return 0

    client = TwitchClient(app_token)
    user_ids = [a.platform_user_id for a in accounts if a.platform_user_id]
    streams = client.get_streams(user_ids)
    live_by_id = {str(s["user_id"]): s for s in streams if s.get("user_id")}

    updated = 0
    now = timezone.now()
    for account in accounts:
        stream = live_by_id.get(account.platform_user_id)
        if stream:
            started = _parse_ts(stream.get("started_at"))
            new_title = (stream.get("title") or "")[:512]
            if (
                not account.is_live
                or account.live_title != new_title
                or account.live_started_at != started
            ):
                account.is_live = True
                account.live_started_at = started
                account.live_title = new_title
                account.last_synced_at = now
                account.save(
                    update_fields=[
                        "is_live",
                        "live_started_at",
                        "live_title",
                        "last_synced_at",
                        "updated_at",
                    ]
                )
                updated += 1
            else:
                account.last_synced_at = now
                account.save(update_fields=["last_synced_at", "updated_at"])
        elif account.is_live:
            account.is_live = False
            account.live_started_at = None
            account.live_title = ""
            account.last_synced_at = now
            account.save(
                update_fields=[
                    "is_live",
                    "live_started_at",
                    "live_title",
                    "last_synced_at",
                    "updated_at",
                ]
            )
            updated += 1
        else:
            account.last_synced_at = now
            account.save(update_fields=["last_synced_at", "updated_at"])
    return updated


def sync_twitch_videos(account: CreatorAccount) -> int:
    token = twitch_app_access_token()
    if not token:
        # Fall back to user token if app token unavailable.
        token = ensure_valid_access_token(account)
    if not token:
        return 0

    videos = TwitchClient(token).get_videos(account.platform_user_id, first=25)
    count = 0
    for video in videos:
        external_id = str(video.get("id") or "")
        if not external_id:
            continue
        CreatorItem.objects.update_or_create(
            provider=CreatorProvider.TWITCH,
            external_id=external_id,
            defaults={
                "account": account,
                "kind": CreatorItemKind.VOD,
                "title": (video.get("title") or "")[:512],
                "url": video.get("url") or "",
                "thumbnail_url": _twitch_thumbnail(video.get("thumbnail_url")),
                "published_at": _parse_ts(video.get("published_at")),
            },
        )
        count += 1
    account.last_synced_at = timezone.now()
    account.save(update_fields=["last_synced_at", "updated_at"])
    return count


def sync_youtube_videos(account: CreatorAccount) -> int:
    token = ensure_valid_access_token(account)
    if not token:
        return 0

    uploads_id = (account.extra or {}).get("uploads_playlist_id") or ""
    if not uploads_id:
        # Re-fetch channel to recover playlist id.
        channel = YouTubeClient(token).get_my_channel()
        if channel:
            related = (channel.get("contentDetails") or {}).get(
                "relatedPlaylists"
            ) or {}
            uploads_id = related.get("uploads") or ""
            extra = dict(account.extra or {})
            extra["uploads_playlist_id"] = uploads_id
            account.extra = extra
            account.save(update_fields=["extra", "updated_at"])
    if not uploads_id:
        return 0

    items = YouTubeClient(token).list_playlist_items(
        uploads_id, max_results=25
    )
    count = 0
    for item in items:
        content = item.get("contentDetails") or {}
        snippet = item.get("snippet") or {}
        video_id = content.get("videoId") or ""
        if not video_id:
            continue
        thumbs = snippet.get("thumbnails") or {}
        thumb = (
            thumbs.get("high")
            or thumbs.get("medium")
            or thumbs.get("default")
            or {}
        ).get("url") or ""
        CreatorItem.objects.update_or_create(
            provider=CreatorProvider.YOUTUBE,
            external_id=video_id,
            defaults={
                "account": account,
                "kind": CreatorItemKind.VIDEO,
                "title": (snippet.get("title") or "")[:512],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": thumb,
                "published_at": _parse_ts(
                    content.get("videoPublishedAt")
                    or snippet.get("publishedAt")
                ),
            },
        )
        count += 1
    account.last_synced_at = timezone.now()
    account.save(update_fields=["last_synced_at", "updated_at"])
    return count


def sync_reddit_posts(account: CreatorAccount) -> int:
    username = account.platform_username or account.platform_user_id
    posts = list_user_submitted(username, limit=25)
    count = 0
    for post in posts:
        external_id = str(post.get("id") or "")
        if not external_id:
            continue
        created = post.get("created_utc")
        published_at = None
        if created is not None:
            try:
                published_at = datetime.fromtimestamp(
                    float(created), tz=dt_timezone.utc
                )
            except (TypeError, ValueError, OSError):
                published_at = None
        CreatorItem.objects.update_or_create(
            provider=CreatorProvider.REDDIT,
            external_id=external_id,
            defaults={
                "account": account,
                "kind": CreatorItemKind.REDDIT_POST,
                "title": (post.get("title") or "")[:512],
                "url": post.get("url") or "",
                "thumbnail_url": post.get("thumbnail") or "",
                "published_at": published_at,
            },
        )
        count += 1
    account.last_synced_at = timezone.now()
    account.save(update_fields=["last_synced_at", "updated_at"])
    return count


def sync_all_media() -> dict[str, int]:
    twitch_count = 0
    youtube_count = 0
    reddit_count = 0
    for account in CreatorAccount.objects.filter(
        provider=CreatorProvider.TWITCH, token_invalid=False
    ):
        twitch_count += sync_twitch_videos(account)
    for account in CreatorAccount.objects.filter(
        provider=CreatorProvider.YOUTUBE, token_invalid=False
    ):
        youtube_count += sync_youtube_videos(account)
    for account in CreatorAccount.objects.filter(
        provider=CreatorProvider.REDDIT
    ):
        reddit_count += sync_reddit_posts(account)
    return {
        "twitch": twitch_count,
        "youtube": youtube_count,
        "reddit": reddit_count,
    }


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value.replace("Z", "+00:00"))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    return dt


def _twitch_thumbnail(template: str | None) -> str:
    if not template:
        return ""
    return (
        template.replace("%{width}", "640")
        .replace("%{height}", "360")
        .replace("{width}", "640")
        .replace("{height}", "360")
    )
