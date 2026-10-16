from datetime import datetime
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


class CorporationRedditPost(Schema):
    corporation_id: int
    exists: bool
    title: str
    content: str
    delivery_method: str
    subreddit: str
    posting_day: str
    posting_time: str
    next_run_at: Optional[datetime] = None
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
