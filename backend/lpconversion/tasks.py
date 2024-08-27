import logging
import requests
import datetime

from app.celery import app

from .models import set_status, update_lp_item, lp_type_ids

base_url = "https://esi.evetech.net/latest"
region_forge = "10000002"
corp_tlf = "1000182"

logger = logging.getLogger(__name__)


class TradedQuantities:
    id: int
    qty_1d: int
    qty_7d: int
    qty_30d: int


def offset_date_string(offset_days):
    return (
        datetime.date.today() - datetime.timedelta(days=offset_days)
    ).strftime("%Y-%m-%d")


def get_item_name(type_id):
    url = base_url + "/universe/types/" + str(type_id) + "/"
    response = requests.get(url, timeout=5)
    return response.json()["name"]


def get_traded_quantities(type_id):
    quantities = TradedQuantities()
    quantities.id = type_id
    quantities.qty_1d = 0
    quantities.qty_7d = 0
    quantities.qty_30d = 0

    url = (
        base_url
        + "/markets/"
        + region_forge
        + "/history/?datasource=tranquility&type_id="
        + str(type_id)
    )
    response = requests.get(url, timeout=5)

    for item in response.json():
        if item["date"] == offset_date_string(1):
            quantities.qty_1d += item["volume"]
        if item["date"] >= offset_date_string(7):
            quantities.qty_7d += item["volume"]
        if item["date"] >= offset_date_string(30):
            quantities.qty_30d += item["volume"]

    return quantities


@app.task()
def update_lpstore_items():
    logger.info("Updating LP store item data...")
    set_status("Updating...")

    for type_id in lp_type_ids:
        item_name = get_item_name(type_id)
        quantities = get_traded_quantities(type_id)
        update_lp_item(
            type_id,
            item_name,
            quantities.qty_1d,
            quantities.qty_7d,
            quantities.qty_30d,
        )

    set_status(
        "Updated " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    logger.info("Updated LP store item data.")
