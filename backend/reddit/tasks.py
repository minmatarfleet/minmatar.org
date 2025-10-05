import logging
import calendar
from datetime import date, datetime

from app.celery import app
from app.errors import create_error_id

from reddit.models import RedditScheduledPost
from reddit.client import RedditClient


@app.task()
def scheduled_reddit_posts():
    today = calendar.day_name[date.today().weekday()]
    logging.info("Scheduled reddit posts for %s", today)

    for post in RedditScheduledPost.objects.filter(posting_day=today):
        logging.info(">  %s", post.title)

        title = post.title.replace("{ID}", create_error_id)

        RedditClient().submit_post(
            subreddit=post.subreddit,
            title=title,
            content=post.content,
        )

        post.last_post_at = datetime.now()
        post.save()
