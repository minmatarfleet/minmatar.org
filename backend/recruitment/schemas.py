from datetime import datetime
from typing import Optional

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
