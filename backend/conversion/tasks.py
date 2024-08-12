import logging

from app.celery import app

logger = logging.getLogger(__name__)


@app.task()
def poc_task():
    logger.info("Celery scheduled task test")
