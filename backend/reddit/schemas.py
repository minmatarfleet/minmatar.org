from datetime import date, datetime
from typing import Optional

from ninja import Schema


class LinkedRedditAccount(Schema):
    username: str
    token_invalid: bool


class MarkdownProblem(Schema):
    # html | image | footnote | task_list (blocking);
    # soft_line_break | fenced_code | heading_space (warnings)
    code: str
    line: int
    excerpt: str
    blocking: bool


class UpcomingSlot(Schema):
    scheduled_for: datetime
    # False: an estimate from next month's draft, which can still move.
    confirmed: bool


class ScheduleChange(Schema):
    created_at: datetime
    slot_date: date
    scheduled_for: datetime
    # True: the post gained this slot; False: it lost it.
    gained: bool
    # rotation | paused | admin
    reason: str


class CorporationRedditPost(Schema):
    corporation_id: int
    exists: bool
    title: str
    content: str
    # alliance | automatic | discord_reminder
    delivery_method: str
    subreddit: str
    paused: bool
    # high | normal
    priority: str
    # active | paused | admin_paused | not_set_up
    rotation_status: str
    interval_days: Optional[int] = None
    upcoming: list[UpcomingSlot] = []
    recent_changes: list[ScheduleChange] = []
    approved: bool
    approved_at: Optional[datetime] = None
    # ready | not_approved | no_account | account_invalid | unscheduled
    automatic_status: str
    last_post_at: Optional[datetime] = None
    last_reddit_post_url: Optional[str] = None
    last_reminder_at: Optional[datetime] = None
    reddit_account: Optional[LinkedRedditAccount] = None
    discord_linked: bool
    markdown_problems: list[MarkdownProblem] = []


class PostSettingsErrorResponse(Schema):
    detail: str
    problems: list[MarkdownProblem] = []


class CorporationRedditPostUpdate(Schema):
    title: str
    content: str
    delivery_method: str
    # Take the post out of the rotation, or put it back. Omit to leave it.
    paused: Optional[bool] = None
