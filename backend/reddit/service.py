import logging

from app.errors import create_error_id

from reddit.client import RedditClient
from reddit.models import RedditPost, RedditPostTemplate
from reddit.scheduling import (
    link_reddit_post_to_discord,
    run_scheduled_posts,
    submit,
)

logger = logging.getLogger(__name__)
client = RedditClient()

__all__ = ["RedditService", "link_reddit_post_to_discord"]


class RedditService:
    """Service (business logic) class for Reddit posts"""

    def post_test(self, subreddit: str):
        logger.info("Reddit API test")

        details = client.get_my_details()
        if details is None:
            return None

        logger.info("Found name: %s", details["name"])

        with open("reddit/posts/rattini.md", encoding="utf-8") as f:
            content = "\n".join(f.readlines())

        post_id = create_error_id()

        client.submit_post(
            subreddit, "Tech team test post " + post_id, content
        )

        return post_id

    def scheduled_posts(self):
        return run_scheduled_posts()

    def post_recriutment_ad(self, template: RedditPostTemplate) -> RedditPost:
        """Submit a post right now (admin action), ignoring the schedule
        and the approval flag."""
        logging.info(">  %s", template.title)
        return submit(template)
