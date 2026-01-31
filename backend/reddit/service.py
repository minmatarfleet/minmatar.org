import logging
import calendar

from django.utils import timezone

from datetime import date
from app.errors import create_error_id

from discord.client import DiscordClient
from reddit.models import RedditScheduledPost
from reddit.client import RedditClient

logger = logging.getLogger(__name__)
client = RedditClient()
discord_client = DiscordClient()


def link_reddit_post_to_discord(
    scheduled_post: RedditScheduledPost,
    reddit_post_url: str,
    title: str,
) -> bool:
    """
    Post a message to the Discord channel attached to the scheduled post,
    linking to the Reddit post. Call this manually or it runs after creating a post.
    Returns True if the message was sent, False otherwise.
    """
    channel_id = scheduled_post.discord_channel_id
    if not channel_id:
        logger.info(
            "No Discord channel configured for scheduled post %s (discord_channel_id=%r)",
            scheduled_post.title,
            scheduled_post.discord_channel_id,
        )
        return False
    message = f"**New Reddit post:** {title}\n{reddit_post_url}"
    try:
        discord_client.create_message(channel_id, message)
        logger.info(
            "Linked Reddit post to Discord channel %s: %s",
            channel_id,
            title,
        )
        return True
    except Exception as e:
        logger.exception(
            "Failed to link Reddit post to Discord channel %s: %s",
            channel_id,
            e,
        )
        return False


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

        result = client.submit_post(
            subreddit=scheduled_post.subreddit,
            title=title,
            content=scheduled_post.content,
            flair_id=scheduled_post.flair_id or None,
        )

        scheduled_post.last_post_at = timezone.now()
        if result and result.get("url"):
            scheduled_post.last_reddit_post_url = result["url"]
            scheduled_post.last_reddit_post_title = title
        scheduled_post.save()

        if result and result.get("url") and scheduled_post.discord_channel_id:
            link_reddit_post_to_discord(
                scheduled_post,
                reddit_post_url=result["url"],
                title=title,
            )

        return title
