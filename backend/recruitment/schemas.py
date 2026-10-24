from datetime import datetime
from typing import Dict, Literal, Optional

from ninja import Schema


class CorporationForumPost(Schema):
    corporation_id: int
    exists: bool
    url: Optional[str] = None
    topic_id: Optional[int] = None
    title: str
    updated_at: Optional[datetime] = None
    last_bumped_at: Optional[datetime] = None


class CorporationForumPostUpdate(Schema):
    # Empty removes the link.
    url: str = ""


class ScoutOutreachRequest(Schema):
    surface: Literal["evejobs", "eve", "forums"]
    thread_url: str
    prospect: str = ""
    seat: str = ""


class ScoutOutreachResponse(Schema):
    code: str
    surface: str
    thread_url: str
    prospect: str
    seat: str
    created_at: datetime
    # Append a target: <link_base>discord, <link_base>learning, ...
    link_base: str
    visitors: int = 0
    first_click_at: Optional[datetime] = None
    # Unique human visitors per target.
    clicks: Dict[str, int] = {}


class ScoutClickRequest(Schema):
    code: str
    target: str
    client_ip: str = ""
    user_agent: str = ""
