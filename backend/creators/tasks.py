from app.celery import app
from creators.post_import import import_recent_creator_posts
from creators.service import poll_twitch_live, sync_all_media
from creators.youtube_announce import announce_new_uploads


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


@app.task(exclusive=10 * 60, expires=10 * 60)
def announce_youtube_uploads():
    """Share new alliance YouTube videos and Shorts in #propaganda."""
    return announce_new_uploads()
