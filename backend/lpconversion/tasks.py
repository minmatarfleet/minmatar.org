import datetime
import logging

import requests

from app.celery import app

from .models import lp_blueprint_ids, lp_type_ids, set_status, update_lp_item

base_url = "https://esi.evetech.net/latest"
region_forge = "10000002"
corp_tlf = "1000182"

logger = logging.getLogger(__name__)


class TradedQuantities:
    id: int
    qty_1d: int
    qty_7d: int
    qty_30d: int
    price: float


def offset_date_string(offset_days):
    return (
        datetime.date.today() - datetime.timedelta(days=offset_days)
    ).strftime("%Y-%m-%d")


def get_item_name(type_id):
    url = base_url + "/universe/types/" + str(type_id) + "/"
    response = requests.get(url, timeout=5)
    return response.json()["name"]


def get_tlf_lp_items():
    url = base_url + "/loyalty/stores/" + corp_tlf + "/offers"
    response = requests.get(url, timeout=5)
    json = response.json()
    data = {}
    for lp_item in json:
        data[lp_item["type_id"]] = lp_item
    return data


def get_traded_quantities(type_id):
    quantities = TradedQuantities()
    quantities.id = type_id
    quantities.qty_1d = 0
    quantities.qty_7d = 0
    quantities.qty_30d = 0
    quantities.price = 0

    url = (
        base_url
        + "/markets/"
        + region_forge
        + "/history/?datasource=tranquility&type_id="
        + str(type_id)
    )
    response = requests.get(url, timeout=5)

    for item in response.json():
        if quantities.price == 0:
            quantities.price = item["average"]
        if item["date"] >= offset_date_string(1):
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

    lp_data = get_tlf_lp_items()

    for type_id in lp_type_ids:
        item_name = get_item_name(type_id)
        quantities = get_traded_quantities(type_id)

        if type_id in lp_blueprint_ids:
            # Get the LP cost of the blueprint, not the item made from it
            item_data = lp_data[lp_blueprint_ids[type_id]]
        else:
            # Get the cost of the item itself
            item_data = lp_data[type_id]

        update_lp_item(
            type_id,
            item_name,
            quantities.qty_1d,
            quantities.qty_7d,
            quantities.qty_30d,
            item_data["quantity"],
            item_data["lp_cost"],
            item_data["isk_cost"],
            quantities.price,
        )

    set_status(
        "Updated " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    logger.info("Updated LP store item data.")
