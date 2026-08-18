"""Parse application timezone answers onto EvePlayer.prime_time."""

from __future__ import annotations

import logging
import re

from django.contrib.auth.models import User

from eveonline.helpers.characters import user_player
from eveonline.models import EvePlayer

logger = logging.getLogger(__name__)

PRIME_TIME_CODES = tuple(choice[0] for choice in EvePlayer.prime_choices)

# Longest labels first so "USTZ - AUTZ" is not treated as "USTZ".
TIMEZONE_LABEL_TO_CODE = (
    ("USTZ - AUTZ", "US_AP"),
    ("AUTZ - EUTZ", "AP_EU"),
    ("EUTZ - USTZ", "EU_US"),
    ("USTZ", "US"),
    ("AUTZ", "AP"),
    ("EUTZ", "EU"),
)

TIMEZONE_LINE_RE = re.compile(r"(?im)^-\s*Timezone:\s*(.+)$")
CODE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z_])(" + "|".join(PRIME_TIME_CODES) + r")(?![A-Za-z_])"
)


def parse_application_prime_time(description: str) -> str | None:
    """Return an EvePlayer.prime_time code from a stored application description."""
    if not description:
        return None

    match = TIMEZONE_LINE_RE.search(description)
    if not match:
        return None

    line = match.group(1).strip()
    bucket = line
    for separator in ("→", "->"):
        if separator in line:
            bucket = line.rsplit(separator, 1)[-1].strip()
            break

    for haystack in (bucket, line):
        parsed = _prime_time_from_text(haystack)
        if parsed:
            return parsed

    return None


def apply_application_prime_time(user: User, description: str) -> None:
    """Set EvePlayer.prime_time from an application description when parseable."""
    prime_time = parse_application_prime_time(description)
    if not prime_time:
        return

    player = user_player(user)
    if not player:
        logger.info(
            "Skipping prime_time update for user %s; no EvePlayer",
            user.id,
        )
        return

    if player.prime_time == prime_time:
        return

    player.prime_time = prime_time
    player.save(update_fields=["prime_time", "modified_at"])
    logger.info(
        "Set prime_time=%s for user %s from corporation application",
        prime_time,
        user.id,
    )


def _prime_time_from_text(text: str) -> str | None:
    for label, code in TIMEZONE_LABEL_TO_CODE:
        if label in text:
            return code

    token = CODE_TOKEN_RE.search(text)
    if token:
        return token.group(1)

    return None
