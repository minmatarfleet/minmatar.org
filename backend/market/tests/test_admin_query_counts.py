"""Query-count smoke tests for market admin context builders."""

from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.db import connection

from app.test import TestCase
from eveonline.models import EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType
from fittings.models import EveFitting, FittingTag
from market.helpers.buy_orders import build_location_buy_orders_context
from market.helpers.contract_admin import build_location_contracts_context
from market.helpers.expectations_admin import (
    build_location_contract_expectations_context,
    build_location_fitting_expectations_context,
)
from market.helpers.sell_orders import build_location_sell_orders_context
from market.models import (
    EveMarketBuyOrderExpectation,
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemOrder,
)


class MarketAdminQueryCountTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.category, _ = EveCategory.objects.get_or_create(
            id=9301,
            defaults={"name": "Module", "published": True},
        )
        cls.group, _ = EveGroup.objects.get_or_create(
            id=9301,
            defaults={
                "name": "Ammo",
                "published": True,
                "eve_category": cls.category,
            },
        )
        cls.item_type, _ = EveType.objects.get_or_create(
            id=9301,
            defaults={
                "name": "Admin Perf Item",
                "published": True,
                "eve_group": cls.group,
            },
        )

    def setUp(self):
        self.location = EveLocation.objects.create(
            location_id=93001,
            location_name="Admin Perf Market",
            short_name="perf",
            market_active=True,
            market_categories=[FittingTag.NANOGANG],
            solar_system_id=1,
            solar_system_name="Test",
        )
        EveMarketItemExpectation.objects.create(
            item=self.item_type,
            location=self.location,
            quantity=10,
        )
        EveMarketItemOrder.objects.create(
            item=self.item_type,
            location=self.location,
            price="100.00",
            quantity=5,
            is_buy_order=False,
        )
        EveMarketBuyOrderExpectation.objects.create(
            item=self.item_type,
            location=self.location,
            quantity=20,
        )
        fitting = EveFitting.objects.create(
            name="[FL33T] Admin Perf",
            eft_format="[Rifter, [FL33T] Admin Perf]\nRifter",
            ship_id=self.item_type.id,
            tags=[FittingTag.NANOGANG],
        )
        EveMarketFittingExpectation.objects.create(
            fitting=fitting,
            location=self.location,
            quantity=2,
        )
        EveMarketContractExpectation.objects.create(
            fitting=fitting,
            location=self.location,
            quantity=1,
        )
        EveMarketContract.objects.create(
            id=930010001,
            status="outstanding",
            title="Perf contract",
            price="1000000.00",
            issuer_external_id=1,
            location=self.location,
            fitting=fitting,
            match_score=0.5,
        )

    def _request(self):
        return self.factory.get("/")

    def test_sell_orders_context_query_count(self):
        with CaptureQueriesContext(connection) as context:
            build_location_sell_orders_context(self.location, self._request())
        self.assertLessEqual(len(context.captured_queries), 30)

    def test_fitting_expectations_context_query_count(self):
        with CaptureQueriesContext(connection) as context:
            build_location_fitting_expectations_context(
                self.location, self._request()
            )
        self.assertLess(len(context.captured_queries), 15)

    def test_contract_expectations_context_query_count(self):
        with CaptureQueriesContext(connection) as context:
            build_location_contract_expectations_context(
                self.location, self._request()
            )
        self.assertLess(len(context.captured_queries), 20)

    def test_buy_orders_context_query_count(self):
        with CaptureQueriesContext(connection) as context:
            build_location_buy_orders_context(self.location)
        self.assertLess(len(context.captured_queries), 10)

    def test_contracts_context_query_count(self):
        with CaptureQueriesContext(connection) as context:
            build_location_contracts_context(self.location)
        self.assertLess(len(context.captured_queries), 5)
