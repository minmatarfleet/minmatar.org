from ninja import Schema


class CreatorAccountSchema(Schema):
    provider: str
    platform_user_id: str
    platform_username: str
    is_live: bool
    live_title: str
    live_started_at: str | None = None
    token_invalid: bool
    last_synced_at: str | None = None


class CreatorLiveSchema(Schema):
    user_id: int
    provider: str
    platform_user_id: str
    platform_username: str
    title: str
    url: str
    started_at: str | None = None


class CreatorFeedItemSchema(Schema):
    provider: str
    kind: str
    external_id: str
    title: str
    url: str
    thumbnail_url: str
    published_at: str | None = None
    platform_username: str
    user_id: int


class RedditUsernameRequest(Schema):
    username: str


class ErrorDetail(Schema):
    detail: str
    feature: str | None = None
