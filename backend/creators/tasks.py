from app.celery import app
from creators.post_import import import_recent_creator_posts
from creators.service import poll_twitch_live, sync_all_media


@app.task(exclusive=10 * 60)
def poll_creator_twitch_live():
    return poll_twitch_live()


@app.task()
def sync_creator_media():
    return sync_all_media()


@app.task(exclusive=30 * 60)
def import_creator_posts():
    """Promote recent linked Reddit/YouTube posts into EvePosts."""
    return import_recent_creator_posts(days=7, state="published")
