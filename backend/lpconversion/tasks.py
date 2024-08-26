import logging
from datetime import datetime

from app.celery import app

from .models import set_status, set_item_data, lp_type_ids

logger = logging.getLogger(__name__)


@app.task()
def update_lpstore_items():
    logger.info("Updating LP store item data...")
    set_status("Updating...")
    data = "type_id, name\n"

    for type_id in lp_type_ids:
        data += str(type_id) + ", 'Unknown'\n"

    set_item_data(data)
    set_status("Test " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Updated LP store item data.")
