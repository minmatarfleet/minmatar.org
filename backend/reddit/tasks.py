from app.celery import app
from reddit.service import RedditService

service = RedditService()


@app.task()
def scheduled_reddit_posts():
    service.scheduled_posts()
