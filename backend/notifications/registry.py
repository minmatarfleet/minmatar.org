"""Code-defined notification type registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from notifications.models import NotificationChannel

ChannelName = str
RenderFn = Callable[[dict], dict]


@dataclass(frozen=True)
class NotificationType:
    key: str
    feature: str
    label: str
    description: str = ""
    channels: tuple[ChannelName, ...] = (
        NotificationChannel.WEB,
        NotificationChannel.DISCORD,
        NotificationChannel.EVE_MAIL,
    )
    defaults: dict[ChannelName, bool] = field(default_factory=dict)
    # Returns channel-specific payload fragments; see ChannelPayload below.
    render: RenderFn | None = None
    # If True, audience may include topic subscribers (broadcast types).
    supports_topic_subscription: bool = False

    def allowed_channels(self) -> tuple[ChannelName, ...]:
        return self.channels

    def default_enabled(self, channel: ChannelName) -> bool:
        if channel in self.defaults:
            return bool(self.defaults[channel])
        # Sensible fallback: web on, others off.
        return channel == NotificationChannel.WEB


_REGISTRY: dict[str, NotificationType] = {}


def register(notification_type: NotificationType) -> NotificationType:
    if notification_type.key in _REGISTRY:
        raise ValueError(
            f"Notification type already registered: {notification_type.key}"
        )
    for channel in notification_type.channels:
        if channel not in NotificationChannel.values:
            raise ValueError(
                f"Unknown channel {channel!r} on {notification_type.key}"
            )
    _REGISTRY[notification_type.key] = notification_type
    return notification_type


def get_type(key: str) -> NotificationType:
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown notification type: {key}") from exc


def all_types() -> list[NotificationType]:
    return sorted(_REGISTRY.values(), key=lambda t: (t.feature, t.key))


def types_for_feature(feature: str) -> list[NotificationType]:
    return [t for t in all_types() if t.feature == feature]


def clear_registry_for_tests() -> None:
    """Test helper only."""
    _REGISTRY.clear()


def iter_features() -> Iterable[str]:
    seen = []
    for t in all_types():
        if t.feature not in seen:
            seen.append(t.feature)
            yield t.feature
