"""Discord DMs for mentor classes and their buttons.

The bot handles the non-link buttons; every prefix here must match
bot/app/custom_ids.py (backend/discord/test_bot_custom_ids.py checks it).
Posted messages keep their custom_ids forever: only add prefixes.
"""

from __future__ import annotations

from datetime import datetime

from app.links import site_url
from notifications.discord_format import feature_color

PASS_CUSTOM_ID_PREFIX = "mentor:pass:"
CANCEL_CUSTOM_ID_PREFIX = "mentor:cancel:"
CONFIRM_CUSTOM_ID_PREFIX = "mentor:confirm:"
# Pilot feedback, 48 hours after the class (one prefix per answer).
RATE_CUSTOM_ID_PREFIXES = {
    "really": "mentor_rate:really:",
    "bit": "mentor_rate:bit:",
    "not": "mentor_rate:not:",
    "didnt_happen": "mentor_rate:none:",
}
# Mentor close-out, 48 hours after the class.
CLOSE_CUSTOM_ID_PREFIXES = {
    "done": "mentor_close:done:",
    "another": "mentor_close:another:",
    "no_show": "mentor_close:noshow:",
    "moved": "mentor_close:moved:",
}

_ACTION_ROW = 1
_BUTTON = 2
_STYLE_PRIMARY = 1
_STYLE_SECONDARY = 2
_STYLE_SUCCESS = 3
_STYLE_DANGER = 4
_STYLE_LINK = 5

MENTEES_PATH = "/learning/mentors/mentees/"
FIND_PATH = "/learning/mentors/"


def pass_custom_id(request_id: int) -> str:
    return f"{PASS_CUSTOM_ID_PREFIX}{int(request_id)}"


def cancel_custom_id(request_id: int) -> str:
    return f"{CANCEL_CUSTOM_ID_PREFIX}{int(request_id)}"


def confirm_custom_id(request_id: int) -> str:
    return f"{CONFIRM_CUSTOM_ID_PREFIX}{int(request_id)}"


def rate_custom_id(answer: str, request_id: int) -> str:
    return f"{RATE_CUSTOM_ID_PREFIXES[answer]}{int(request_id)}"


def close_custom_id(answer: str, request_id: int) -> str:
    return f"{CLOSE_CUSTOM_ID_PREFIXES[answer]}{int(request_id)}"


def discord_profile_url(discord_user_id: int) -> str:
    return f"https://discord.com/users/{int(discord_user_id)}"


def handle(tag: str) -> str:
    """A Discord username from its stored tag ("orionsasolo#0")."""
    name, _, discriminator = (tag or "").partition("#")
    if discriminator and discriminator != "0":
        return f"{name}#{discriminator}"
    return name


def _button(label, *, custom_id=None, url=None, style=_STYLE_SECONDARY):
    button = {"type": _BUTTON, "label": label}
    if url:
        button.update(style=_STYLE_LINK, url=url)
    else:
        button.update(style=style, custom_id=custom_id)
    return button


def _row(*buttons) -> dict:
    return {"type": _ACTION_ROW, "components": list(buttons)}


def _embed(title, description="", fields=None, thumbnail="", url=""):
    embed = {
        "author": {"name": "Mentors"},
        "title": title,
        "color": feature_color("learning"),
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = [
            {"name": name, "value": value or "—", "inline": True}
            for name, value in fields
        ]
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    if url:
        embed["url"] = url
    return embed


def _when(starts_at: datetime) -> str:
    """Discord renders <t:...> in each reader's own clock."""
    stamp = int(starts_at.timestamp())
    return f"<t:{stamp}:F> (<t:{stamp}:R>)\n{starts_at:%a %d %b, %H:%M} EVE"


def request_payload(
    *,
    request_id: int,
    pilot_name: str,
    pilot_portrait: str,
    pilot_handle: str,
    pilot_corp: str,
    class_title: str,
    plays: str,
    fits: str,
    note: str,
    passed_on: bool,
) -> dict:
    title = f"{pilot_name} asked you for a class"
    if passed_on:
        title += " (another mentor couldn't take it)"
    description = f"> {note}" if note else ""
    embed = _embed(
        title,
        description,
        [
            ("Class", class_title),
            ("Plays", plays),
            ("Discord", f"@{pilot_handle}" if pilot_handle else ""),
            ("Corp", pilot_corp),
            ("Fits you", fits),
        ],
        thumbnail=pilot_portrait,
    )
    return {
        "content": "No answer in 2 days and it goes to the next mentor who fits.",
        "embeds": [embed],
        "components": [
            _row(
                _button("Accept and pick a time", url=site_url(MENTEES_PATH)),
                _button("Pass", custom_id=pass_custom_id(request_id)),
            )
        ],
    }


def booked_payload(
    *,
    request_id: int,
    other_name: str,
    other_portrait: str,
    other_handle: str,
    other_discord_id: int | None,
    class_title: str,
    starts_at: datetime,
    bring: str,
    as_mentor: bool,
) -> dict:
    title = (
        f"You're teaching {class_title} to {other_name}"
        if as_mentor
        else f"{other_name} will teach you {class_title}"
    )
    first = other_name.split(" ")[0]
    embed = _embed(
        title,
        fields=[
            ("When", _when(starts_at)),
            (
                f"{first} on Discord",
                f"@{other_handle}" if other_handle else "",
            ),
            ("Bring", bring),
        ],
        thumbnail=other_portrait,
    )
    buttons = []
    if other_discord_id:
        buttons.append(
            _button(
                f"Message {first}",
                url=discord_profile_url(other_discord_id),
            )
        )
    buttons.append(
        _button("I can't make it", custom_id=cancel_custom_id(request_id))
    )
    hello = (
        f"Send @{other_handle} a friend request and say hello. "
        f"{first} has your name too."
        if other_handle
        else ""
    )
    return {
        "content": hello,
        "embeds": [embed],
        "components": [_row(*buttons)],
    }


def reminder_payload(
    *,
    request_id: int,
    other_name: str,
    other_discord_id: int | None,
    class_title: str,
    starts_at: datetime,
    bring: str,
) -> dict:
    first = other_name.split(" ")[0]
    text = (
        f"Reminder: **{class_title} with {other_name}** is "
        f"<t:{int(starts_at.timestamp())}:F>."
    )
    if bring:
        text += f" Bring {bring[0].lower()}{bring[1:]}."
    buttons = [
        _button(
            "I'll be there",
            custom_id=confirm_custom_id(request_id),
            style=_STYLE_SUCCESS,
        )
    ]
    if other_discord_id:
        buttons.append(
            _button(
                f"Message {first}", url=discord_profile_url(other_discord_id)
            )
        )
    buttons.append(
        _button("Cancel the class", custom_id=cancel_custom_id(request_id))
    )
    return {
        "content": text + "\nCancel tells "
        f"{first} straight away and frees the slot.",
        "components": [_row(*buttons)],
    }


def pilot_feedback_payload(
    *, request_id: int, mentor_name: str, class_title: str
) -> dict:
    first = mentor_name.split(" ")[0]
    return {
        "content": (
            f"How did your **{class_title}** class with {mentor_name} go?\n"
            f"-# Only alliance leadership sees this. {first} doesn't."
        ),
        "components": [
            _row(
                _button(
                    "Really helped",
                    custom_id=rate_custom_id("really", request_id),
                ),
                _button(
                    "Helped a bit", custom_id=rate_custom_id("bit", request_id)
                ),
                _button(
                    "Didn't help", custom_id=rate_custom_id("not", request_id)
                ),
                _button(
                    "It didn't happen",
                    custom_id=rate_custom_id("didnt_happen", request_id),
                ),
            )
        ],
    }


def mentor_followup_payload(
    *, request_id: int, pilot_name: str, class_title: str
) -> dict:
    first = pilot_name.split(" ")[0]
    return {
        "content": (
            f"Did your **{class_title}** class with {pilot_name} happen?\n"
            f"-# Your notes go to alliance leadership, not to {first}."
        ),
        "components": [
            _row(
                _button(
                    "Yes, done",
                    custom_id=close_custom_id("done", request_id),
                    style=_STYLE_SUCCESS,
                ),
                _button(
                    "Yes, needs another class",
                    custom_id=close_custom_id("another", request_id),
                ),
                _button(
                    "No-show", custom_id=close_custom_id("no_show", request_id)
                ),
                _button(
                    "We moved it",
                    custom_id=close_custom_id("moved", request_id),
                ),
            )
        ],
    }


def text_payload(text: str, link_label: str = "", path: str = "") -> dict:
    payload: dict = {"content": text}
    if link_label and path:
        payload["components"] = [_row(_button(link_label, url=site_url(path)))]
    return payload
