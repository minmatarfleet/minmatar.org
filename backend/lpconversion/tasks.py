import logging

from app.celery import app

from .models import set_status

logger = logging.getLogger(__name__)


@app.task()
def update_lpstore_items():
    logger.info("Updating LP store item data")
    set_status("Testing")
