from ninja import Router
from django.http import HttpResponse
from pydantic import BaseModel
from typing import List
import csv
import requests
import datetime


class ItemsResponse(BaseModel):
    id: int
    name: str
    qty_1d: int
    qty_7d: int
    qty_30d: int


router = Router(tags=["Conversion"])

type_ids = [
    41490,
    32006,
    32014,
    21894,
    21896,
    21898,
    21902,
    21904,
    21906,
    21918,
    21922,
    21924,
    31932,
    31928,
    31924,
    31944,
    41212,
    41215,
    41218,
    33157,
    29336,
    17713,
    72811,
    31890,
    31888,
    31892,
    31894,
]

blueprint_ids = {
    # Blueprint: Item
    33158: 33157,
    72923: 72811,
    29339: 29336,
    17714: 17713,
}

base_url = "https://esi.evetech.net/latest"
region_forge = "10000002"
corp_tlf = "1000182"

items = []

last_refresh = datetime.datetime.min


@router.get(
    "",
    response={200: List[ItemsResponse]},
    description="Get LP store item data in JSON format",
)
def get_lp_items(request):
    return items


@router.get("/csv", description="Get LP store item data in CSV format")
def send_csv(request):
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lp_items.csv"'},
    )
    writer = csv.writer(response)
    writer.writerow(["Item ID", "Name", "Qty 1d", "Qty 7d", "Qty 30d"])

    for item in items:
        writer.writerow(
            [item.id, item.name, item.qty_1d, item.qty_7d, item.qty_30d]
        )

    return response


def get_item_name(item_id):
    url = base_url + "/universe/types/" + str(item_id) + "/"
    response = requests.get(url, timeout=5)
    return response.json()["name"]


def date_string(offset):
    return (datetime.date.today() - datetime.timedelta(days=offset)).strftime(
        "%Y-%m-%d"
    )


def update_traded_quantity(item_id):
    url = (
        base_url
        + "/markets/"
        + region_forge
        + "/history/?datasource=tranquility&type_id="
        + str(item_id)
    )
    response = requests.get(url, timeout=5)
    total_1d = 0
    total_7d = 0
    total_30d = 0
    for item in response.json():
        if item["date"] == date_string(1):
            total_1d += item["volume"]
        if item["date"] >= date_string(7):
            total_7d += item["volume"]
        if item["date"] >= date_string(30):
            total_30d += item["volume"]

    item = ItemsResponse(
        id=item_id,
        name=get_item_name(item_id),
        qty_1d=total_1d,
        qty_7d=total_7d,
        qty_30d=total_30d,
    )

    items.append(item)


def update_traded_quantities():
    items.clear()

    for item in type_ids:
        update_traded_quantity(item)


@router.get(
    "/refresh",
    response={200: str},
    description="Refresh the market data; can take a while to complete.",
)
def refresh_data(request):
    global last_refresh
    print(last_refresh)
    if (datetime.datetime.now() - last_refresh) < datetime.timedelta(hours=2):
        return (
            "LP store items not refreshed, last refresh was "
            + last_refresh.strftime("%Y-%m-%d %H:%M:%S")
        )

    update_traded_quantities()
    last_refresh = datetime.datetime.now()
    return "LP store items refreshed"
