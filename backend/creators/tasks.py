from app.celery import app
from app.locks import overlap_guard
from creators.service import poll_twitch_live, sync_all_media


@app.task()
@overlap_guard(ttl=10 * 60)
def poll_creator_twitch_live():
    return poll_twitch_live()


@app.task()
def sync_creator_media():
    return sync_all_media()
