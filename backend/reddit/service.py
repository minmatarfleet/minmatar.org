import logging
import calendar

from django.utils import timezone

from datetime import date
from app.errors import create_error_id

from reddit.models import RedditScheduledPost
from reddit.client import RedditClient

logger = logging.getLogger(__name__)
client = RedditClient()


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
        today = calendar.day_name[date.today().weekday()]
        logging.info("Scheduled reddit posts for %s", today)

        for scheduled_post in RedditScheduledPost.objects.filter(
            posting_day=today
        ):
            self.post_recriutment_ad(scheduled_post)

    def post_recriutment_ad(self, scheduled_post):
        title = scheduled_post.title.replace("{ID}", create_error_id())

        logging.info(">  %s", scheduled_post.title)

        client.submit_post(
            subreddit=scheduled_post.subreddit,
            title=title,
            content=scheduled_post.content,
        )

        scheduled_post.last_post_at = timezone.now()
        scheduled_post.save()

        return title
