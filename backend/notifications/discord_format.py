"""Feature branding for Discord notification embeds."""

from __future__ import annotations

# Human labels for notification `feature` keys (registry field).
FEATURE_LABELS: dict[str, str] = {
    "industry": "Industry",
}

# Discord embed accent colors (decimal).
FEATURE_COLORS: dict[str, int] = {
    "industry": 0xC45C26,  # Minmatar-ish orange
}

_DEFAULT_COLOR = 0x4A5568


def feature_label(feature: str | None) -> str:
    if not feature:
        return "Notification"
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").title())


def feature_color(feature: str | None) -> int:
    if not feature:
        return _DEFAULT_COLOR
    return FEATURE_COLORS.get(feature, _DEFAULT_COLOR)


def discord_embed_from_payload(payload: dict) -> dict:
    """
    Build a Discord embed that shows which product area the ping is from.

    Uses `feature` / `feature_label` on the payload (set by the notify service)
    plus the existing title / discord_message / url fields.
    """
    label = payload.get("feature_label") or feature_label(
        payload.get("feature")
    )
    description = (
        payload.get("discord_message") or payload.get("body") or ""
    ).strip()
    embed: dict = {
        "author": {"name": label},
        "color": feature_color(payload.get("feature")),
    }
    if description:
        embed["description"] = description

    title = (payload.get("title") or "").strip()
    # Avoid repeating the same heading when discord_message already leads with it.
    if title and not _description_starts_with_title(description, title):
        embed["title"] = title

    # Discord only hyperlinks embed.url when title is set.
    url = (payload.get("url") or "").strip()
    if url and embed.get("title"):
        embed["url"] = url

    return embed


def _description_starts_with_title(description: str, title: str) -> bool:
    if not description or not title:
        return False
    first_line = description.lstrip().split("\n", 1)[0]
    # Strip markdown heading markers / backticks for a loose match.
    normalized = first_line.replace("#", "").replace("`", "").strip().lower()
    return normalized == title.lower() or normalized.startswith(title.lower())
