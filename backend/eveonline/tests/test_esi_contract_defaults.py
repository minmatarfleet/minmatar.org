"""esi_contract_defaults matches the two hand-written mappers it replaced."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase

from eveonline.helpers.esi import esi_contract_defaults, parse_esi_date

FULL = {
    "contract_id": 1,
    "type": "courier",
    "status": "outstanding",
    "availability": "personal",
    "issuer_id": 10,
    "issuer_corporation_id": 20,
    "assignee_id": 30,
    "acceptor_id": 0,
    "for_corporation": True,
    "date_issued": "2026-10-01T12:00:00Z",
    "date_expired": "2026-10-15T12:00:00+00:00",
    "date_accepted": datetime(2026, 10, 2, 8, 30),
    "date_completed": None,
    "days_to_complete": 3,
    "price": 0.0,
    "reward": 12500000.5,
    "collateral": 1e9,
    "buyout": None,
    "volume": 12345.67,
    "start_location_id": 60003760,
    "end_location_id": 1022734985679,
    "title": "Jita -> Amamake",
}
SPARSE = {"contract_id": 2, "issuer_id": 10}


def _old_mapping(raw, parse):
    """The inline mapping both sync functions used, minus the owner key."""
    price = raw.get("price")
    if price is not None:
        price = Decimal(str(price))
    reward = raw.get("reward")
    if reward is not None:
        reward = Decimal(str(reward))
    collateral = raw.get("collateral")
    if collateral is not None:
        collateral = Decimal(str(collateral))
    buyout = raw.get("buyout")
    if buyout is not None:
        buyout = Decimal(str(buyout))
    volume = raw.get("volume")
    if volume is not None:
        volume = Decimal(str(volume))
    return {
        "type": raw.get("type", ""),
        "status": raw.get("status", ""),
        "availability": raw.get("availability", ""),
        "issuer_id": raw.get("issuer_id"),
        "issuer_corporation_id": raw.get("issuer_corporation_id"),
        "assignee_id": raw.get("assignee_id"),
        "acceptor_id": raw.get("acceptor_id"),
        "for_corporation": raw.get("for_corporation", False),
        "date_issued": parse(raw.get("date_issued")),
        "date_expired": parse(raw.get("date_expired")),
        "date_accepted": parse(raw.get("date_accepted")),
        "date_completed": parse(raw.get("date_completed")),
        "days_to_complete": raw.get("days_to_complete"),
        "price": price,
        "reward": reward,
        "collateral": collateral,
        "buyout": buyout,
        "volume": volume,
        "start_location_id": raw.get("start_location_id"),
        "end_location_id": raw.get("end_location_id"),
        "title": raw.get("title", ""),
    }


class EsiContractDefaultsTest(SimpleTestCase):
    def test_matches_the_old_mapping(self):
        for raw in (FULL, SPARSE):
            self.assertEqual(
                esi_contract_defaults(raw), _old_mapping(raw, parse_esi_date)
            )

    def test_values(self):
        defaults = esi_contract_defaults(FULL)
        self.assertEqual(defaults["reward"], Decimal("12500000.5"))
        self.assertEqual(defaults["price"], Decimal("0.0"))
        self.assertIsNone(defaults["buyout"])
        self.assertEqual(
            defaults["date_issued"],
            datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc),
        )
        self.assertIsNotNone(defaults["date_accepted"].tzinfo)
        self.assertEqual(esi_contract_defaults(SPARSE)["type"], "")
