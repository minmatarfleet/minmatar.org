"""Notification preferences and topic subscription API."""

from typing import List

from ninja import Router, Schema
from pydantic import Field

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from notifications.ack import AckError, ack_delivery_for_requester
from notifications.models import (
    NotificationChannel,
    NotificationPreference,
    NotificationTopicSubscription,
)
from notifications.registry import all_types, get_type
from notifications.service import effective_preferences

router = Router(tags=["Notifications"])


class ChannelPreferenceSchema(Schema):
    channel: str
    enabled: bool
    allowed: bool = True


class NotificationTypeSchema(Schema):
    key: str
    feature: str
    label: str
    description: str
    supports_topic_subscription: bool
    topic_subscribed: bool = False
    channels: List[ChannelPreferenceSchema]


class FeaturePreferencesSchema(Schema):
    feature: str
    types: List[NotificationTypeSchema]


class PreferenceUpdateItem(Schema):
    notification_type: str
    channel: str
    enabled: bool


class PreferenceUpdateRequest(Schema):
    preferences: List[PreferenceUpdateItem] = Field(default_factory=list)


@router.get(
    "/preferences",
    response={200: List[FeaturePreferencesSchema]},
    auth=AuthBearer(),
)
def get_preferences(request):
    prefs = effective_preferences(request.user)
    topic_keys = set(
        NotificationTopicSubscription.objects.filter(
            user=request.user
        ).values_list("notification_type", flat=True)
    )
    by_feature: dict[str, list] = {}
    for ntype in all_types():
        channel_prefs = []
        for channel in NotificationChannel.values:
            allowed = channel in ntype.allowed_channels()
            enabled = prefs.get(ntype.key, {}).get(
                channel, ntype.default_enabled(channel) if allowed else False
            )
            if not allowed:
                continue
            channel_prefs.append(
                ChannelPreferenceSchema(
                    channel=channel,
                    enabled=enabled,
                    allowed=True,
                )
            )
        by_feature.setdefault(ntype.feature, []).append(
            NotificationTypeSchema(
                key=ntype.key,
                feature=ntype.feature,
                label=ntype.label,
                description=ntype.description,
                supports_topic_subscription=ntype.supports_topic_subscription,
                topic_subscribed=ntype.key in topic_keys,
                channels=channel_prefs,
            )
        )
    return [
        FeaturePreferencesSchema(feature=feature, types=types)
        for feature, types in sorted(by_feature.items())
    ]


@router.put(
    "/preferences",
    response={200: List[FeaturePreferencesSchema], 400: ErrorResponse},
    auth=AuthBearer(),
)
def put_preferences(request, payload: PreferenceUpdateRequest):
    validated: list[tuple[str, str, bool]] = []
    for item in payload.preferences:
        try:
            ntype = get_type(item.notification_type)
        except KeyError:
            return 400, ErrorResponse(
                detail=f"Unknown notification type: {item.notification_type}"
            )
        if item.channel not in ntype.allowed_channels():
            return 400, ErrorResponse(
                detail=(
                    f"Channel {item.channel} not allowed for "
                    f"{item.notification_type}"
                )
            )
        validated.append((item.notification_type, item.channel, item.enabled))

    with transaction.atomic():
        for notification_type, channel, enabled in validated:
            NotificationPreference.objects.update_or_create(
                user=request.user,
                notification_type=notification_type,
                channel=channel,
                defaults={"enabled": enabled},
            )
    return get_preferences(request)


@router.post(
    "/topics/{type_key}",
    response={201: dict, 400: ErrorResponse},
    auth=AuthBearer(),
)
def subscribe_topic(request, type_key: str):
    try:
        ntype = get_type(type_key)
    except KeyError:
        return 400, ErrorResponse(detail=f"Unknown type: {type_key}")
    if not ntype.supports_topic_subscription:
        return 400, ErrorResponse(
            detail=f"Type {type_key} does not support topic subscription"
        )
    NotificationTopicSubscription.objects.get_or_create(
        user=request.user, notification_type=type_key
    )
    return 201, {"notification_type": type_key, "subscribed": True}


@router.delete(
    "/topics/{type_key}",
    response={204: None, 400: ErrorResponse},
    auth=AuthBearer(),
)
def unsubscribe_topic(request, type_key: str):
    try:
        get_type(type_key)
    except KeyError:
        return 400, ErrorResponse(detail=f"Unknown type: {type_key}")
    NotificationTopicSubscription.objects.filter(
        user=request.user, notification_type=type_key
    ).delete()
    return 204, None


class AckDeliveryRequest(Schema):
    discord_user_id: int


class AckDeliveryResponse(Schema):
    id: int
    status: str
    delete_message: bool = True


@router.post(
    "/deliveries/{delivery_id}/ack",
    response={
        200: AckDeliveryResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Mark a Discord notification delivery as read (bot / user)",
)
def ack_delivery(request, delivery_id: int, payload: AckDeliveryRequest):
    """
    Called by the Discord bot when the user clicks Mark as read.

    Owners may ack their own deliveries. Staff/superuser tokens (bot service)
    may ack on behalf of a Discord user after ownership checks.
    """
    try:
        delivery = ack_delivery_for_requester(
            delivery_id,
            requester=request.user,
            discord_user_id=payload.discord_user_id,
        )
    except AckError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))

    return 200, AckDeliveryResponse(
        id=delivery.id,
        status=delivery.status,
        delete_message=True,
    )
