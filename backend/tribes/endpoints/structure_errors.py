"""Turn structure helper failures into API responses."""

import logging

import requests
from django.db import IntegrityError

from app.errors import ErrorResponse
from discord.exceptions import DiscordRoleAssignmentError
from tribes.helpers.structure import StructureError

logger = logging.getLogger(__name__)

DISCORD_FAILED = (
    "Discord didn't create or rename the role, so nothing was changed. "
    "Try again in a minute."
)


def run(change):
    """``(None, result)``, or ``((status, ErrorResponse), None)``."""
    try:
        return None, change()
    except StructureError as exc:
        return (exc.status_code, ErrorResponse(detail=str(exc))), None
    except IntegrityError:
        # Two people creating the same name at once: the checks passed for
        # both, the database refused the second.
        return (
            400,
            ErrorResponse(detail="That name or slug was just taken."),
        ), None
    except (requests.RequestException, DiscordRoleAssignmentError):
        logger.exception("Discord failed during a tribe structure change")
        return (502, ErrorResponse(detail=DISCORD_FAILED)), None
