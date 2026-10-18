"""API shapes shared by every app that shows tribe-group content.

Kept out of tribes.endpoints so fleets and posts can import them without
loading the tribes routers.
"""

from typing import Optional

from pydantic import BaseModel


class HostGroupRef(BaseModel):
    """The tribe group a fleet, post or event is published as."""

    id: int
    code: str
    name: str
    tribe_id: int
    tribe_name: str


class RestrictedResponse(BaseModel):
    """403 for a members-only item: names the group, hides the content."""

    detail: str
    host_group: Optional[HostGroupRef] = None


MEMBERS_ONLY_DETAIL = "members_only"


def restricted(host_group_ref: dict | None) -> tuple[int, dict]:
    """The 403 body for a members-only item the viewer can't see."""
    return 403, {"detail": MEMBERS_ONLY_DETAIL, "host_group": host_group_ref}
