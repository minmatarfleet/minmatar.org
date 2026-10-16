"""The CEO's link to their corporation's EVE forums recruitment thread."""

from recruitment.forums import (
    ForumUrlError,
    TopicNotFound,
    fetch_topic,
    in_recruitment_center,
    parse_topic_url,
    topic_url,
)
from recruitment.models import ForumRecruitmentPost

TITLE_MAX = ForumRecruitmentPost._meta.get_field("title").max_length


class ForumPostError(ValueError):
    """Invalid CEO input. `code` names the problem for the frontend."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def forum_post_settings(corporation) -> dict:
    post = ForumRecruitmentPost.objects.filter(corporation=corporation).first()
    return {
        "corporation_id": corporation.corporation_id,
        "exists": post is not None,
        "url": post.url if post else None,
        "topic_id": post.topic_id if post else None,
        "title": post.title if post else "",
        "updated_at": post.updated_at if post else None,
        "last_bumped_at": post.last_bumped_at if post else None,
    }


def remove_forum_post(corporation) -> None:
    ForumRecruitmentPost.objects.filter(corporation=corporation).delete()


def save_forum_post(corporation, url: str, user) -> ForumRecruitmentPost:
    """Link (or re-link) the corporation's thread. The forum is checked
    when it answers; if it can't be reached the link is saved anyway."""
    try:
        parsed = parse_topic_url(url)
    except ForumUrlError as e:
        raise ForumPostError(e.code) from e

    taken = (
        ForumRecruitmentPost.objects.filter(topic_id=parsed.topic_id)
        .exclude(corporation=corporation)
        .exists()
    )
    if taken:
        raise ForumPostError("thread_linked_elsewhere")

    try:
        topic = fetch_topic(parsed.topic_id)
    except TopicNotFound as e:
        raise ForumPostError("thread_not_found") from e

    post = ForumRecruitmentPost.objects.filter(corporation=corporation).first()
    same_thread = post is not None and post.topic_id == parsed.topic_id
    title = post.title if same_thread else ""
    canonical_url = parsed.url
    if topic is not None:
        if not in_recruitment_center(topic):
            raise ForumPostError("not_recruitment_center")
        title = str(topic.get("title") or "")[:TITLE_MAX]
        # The forum's slug follows title edits; the one typed may be stale.
        if isinstance(topic.get("slug"), str) and topic["slug"]:
            canonical_url = topic_url(topic["slug"], parsed.topic_id)

    if post is None:
        post = ForumRecruitmentPost(corporation=corporation)
    if not same_thread:
        post.linked_by = user
        post.last_bumped_at = None
    post.url = canonical_url
    post.topic_id = parsed.topic_id
    post.title = title
    post.save()
    return post
