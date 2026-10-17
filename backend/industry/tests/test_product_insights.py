"""Tests for supply chain product insights (rollup, cache and endpoint)."""

import importlib
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterAsset,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCorporation,
    EveCorporationIndustryJob,
    EveLocation,
    EvePlayer,
)
from eveuniverse.models import (
    EveCategory,
    EveConstellation,
    EveGroup,
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveRegion,
    EveSolarSystem,
    EveType,
)
from market.models import (
    EveMarketContract,
    EveMarketContractItem,
    EveMarketInferredSale,
)

from app.test import TestCase as AppTestCase
from industry.helpers.product_insights import (
    compute_product_insights,
    product_insights,
)
from industry.models import IndustryOrderItem, IndustryProduct
from industry.test_utils import create_industry_order

ALLIANCE_ID = 99011978
SHIP_TYPE_ID = 990001
BLUEPRINT_TYPE_ID = 990002
COMPONENT_TYPE_ID = 990003
UNTRACKED_TYPE_ID = 990004
AMAMAKE_ID = 30002537
HUOLA_ID = 30003067


def _system(system_id, name):
    region, _ = EveRegion.objects.get_or_create(
        id=10000030, defaults={"name": "Heimatar"}
    )
    constellation, _ = EveConstellation.objects.get_or_create(
        id=20000334,
        defaults={
            "name": "Anher",
            "eve_region": region,
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
        },
    )
    return EveSolarSystem.objects.create(
        id=system_id,
        name=name,
        eve_constellation=constellation,
        security_status=0.4,
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        enabled_sections=0,
    )


def _job(model, job_id, end_date, runs=1, status="delivered", **kwargs):
    return model.objects.create(
        job_id=job_id,
        activity_id=1,
        blueprint_id=job_id,
        blueprint_type_id=BLUEPRINT_TYPE_ID,
        blueprint_location_id=1,
        facility_id=1,
        location_id=1,
        output_location_id=1,
        status=status,
        start_date=end_date - timedelta(hours=1),
        end_date=end_date,
        duration=3600,
        runs=runs,
        **kwargs,
    )


class ProductInsightsTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.now = timezone.now()
        ship_category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        other_category = EveCategory.objects.create(
            id=17, name="Commodity", published=True
        )
        ships = EveGroup.objects.create(
            id=27,
            name="Battleship",
            published=True,
            eve_category=ship_category,
        )
        commodities = EveGroup.objects.create(
            id=334,
            name="Construction Components",
            published=True,
            eve_category=other_category,
        )
        self.ship = EveType.objects.create(
            id=SHIP_TYPE_ID, name="Test Hull", published=True, eve_group=ships
        )
        blueprint = EveType.objects.create(
            id=BLUEPRINT_TYPE_ID,
            name="Test Hull Blueprint",
            published=True,
            eve_group=commodities,
        )
        self.component = EveType.objects.create(
            id=COMPONENT_TYPE_ID,
            name="Test Component",
            published=True,
            eve_group=commodities,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=blueprint,
            activity_id=1,
            product_eve_type=self.ship,
            quantity=1,
        )
        self.product = IndustryProduct.objects.create(
            eve_type=self.ship, strategy="imported"
        )
        self.component_product = IndustryProduct.objects.create(
            eve_type=self.component, strategy="imported"
        )

        EveAlliance.objects.create(alliance_id=ALLIANCE_ID, name="Ours")
        main_user = User.objects.create(username="builder")
        self.main = EveCharacter.objects.create(
            character_id=2001,
            character_name="Main Builder",
            user=main_user,
            alliance_id=ALLIANCE_ID,
        )
        self.alt = EveCharacter.objects.create(
            character_id=2002,
            character_name="Builder Alt",
            user=main_user,
            alliance_id=ALLIANCE_ID,
        )
        EvePlayer.objects.create(
            nickname="builder", user=main_user, primary_character=self.main
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=3001, name="Build Corp"
        )
        self.location = EveLocation.objects.create(
            location_id=6001,
            location_name="Amamake Freeport",
            solar_system_id=1,
            solar_system_name="Amamake",
            market_active=True,
        )

    def _insights(self):
        return compute_product_insights(self.now)[self.product.pk]

    def test_builders_merge_alts_and_corp_jobs(self):
        _job(
            EveCharacterIndustryJob,
            1,
            self.now - timedelta(days=3),
            runs=2,
            character=self.alt,
            installer_id=self.alt.character_id,
        )
        _job(
            EveCorporationIndustryJob,
            2,
            self.now - timedelta(days=40),
            runs=3,
            corporation=self.corporation,
            installer_id=self.main.character_id,
        )
        # Too old for the window, and still running: neither is "built".
        _job(
            EveCharacterIndustryJob,
            3,
            self.now - timedelta(days=200),
            character=self.main,
            installer_id=self.main.character_id,
        )
        _job(
            EveCharacterIndustryJob,
            4,
            self.now + timedelta(days=1),
            runs=5,
            status="active",
            character=self.main,
            installer_id=self.main.character_id,
        )

        data = self._insights()

        self.assertEqual(data["built"]["units_90d"], 5)
        self.assertEqual(data["built"]["units_30d"], 2)
        self.assertEqual(data["built"]["jobs_90d"], 2)
        self.assertEqual(data["built"]["running_units"], 5)
        self.assertEqual(data["built"]["builders_90d"], 1)
        [builder] = data["builders"]
        self.assertEqual(builder["character_id"], self.main.character_id)
        self.assertEqual(builder["character_name"], "Main Builder")
        self.assertEqual(builder["units"], 5)
        self.assertEqual(
            data["corporations"],
            [
                {
                    "corporation_id": 3001,
                    "corporation_name": "Build Corp",
                    "units": 3,
                }
            ],
        )
        self.assertEqual(sum(week["built"] for week in data["weekly"]), 5)
        [running] = data["running"]
        self.assertEqual(running["character_name"], "Main Builder")
        self.assertEqual(running["units"], 5)
        self.assertEqual(running["corporation_name"], "")

    def test_orders_sales_hangars_and_losses(self):
        order = create_industry_order(
            needed_by=date.today() + timedelta(days=7), character=self.main
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=self.ship, quantity=4
        )
        EveMarketInferredSale.objects.create(
            location=self.location,
            item=self.ship,
            quantity=2,
            price=100,
            inferred_at=self.now - timedelta(days=2),
            reason="sellout",
        )
        contract = EveMarketContract.objects.create(
            id=1,
            status="finished",
            title="Test Hull",
            price=200,
            issuer_external_id=1,
            completed_at=self.now - timedelta(days=50),
        )
        EveMarketContractItem.objects.create(
            contract=contract, type_id=SHIP_TYPE_ID, quantity=1
        )
        EveCharacterAsset.objects.create(
            type_id=SHIP_TYPE_ID,
            type_name="Test Hull",
            location_id=6001,
            location_name="Amamake Freeport",
            character=self.main,
        )
        EveCharacterAsset.objects.create(
            type_id=SHIP_TYPE_ID,
            type_name="Test Hull",
            location_id=6001,
            location_name="Amamake Freeport",
            character=self.alt,
        )
        # The same kill seen by two of our pilots counts once; a kill on a
        # pilot outside our alliances does not count.
        for row_id, holder in ((1, self.main), (2, self.alt)):
            EveCharacterKillmail.objects.create(
                id=row_id,
                killmail_id=500,
                killmail_hash="x",
                killmail_time=self.now - timedelta(days=1),
                solar_system_id=30002537,
                ship_type_id=SHIP_TYPE_ID,
                victim_character_id=self.alt.character_id,
                victim_alliance_id=ALLIANCE_ID,
                attackers="[]",
                items="[]",
                character=holder,
            )
        EveCharacterKillmail.objects.create(
            id=3,
            killmail_id=501,
            killmail_hash="y",
            killmail_time=self.now - timedelta(days=1),
            solar_system_id=30002537,
            ship_type_id=SHIP_TYPE_ID,
            victim_character_id=9999,
            victim_alliance_id=1,
            attackers="[]",
            items="[]",
            character=self.main,
        )

        data = self._insights()

        self.assertEqual(data["orders"]["open_orders"], 1)
        self.assertEqual(data["orders"]["open_units"], 4)
        self.assertEqual(data["orders"]["recent"][0]["quantity"], 4)
        self.assertEqual(data["sales"]["market_units_30d"], 2)
        self.assertEqual(data["sales"]["contract_units_30d"], 0)
        self.assertEqual(data["sales"]["contract_units_90d"], 1)
        self.assertEqual(
            data["sales"]["locations"],
            [{"location_name": "Amamake Freeport", "units": 2}],
        )
        self.assertEqual(data["hangars"]["units"], 2)
        self.assertEqual(data["hangars"]["pilots"], 1)
        self.assertEqual(data["losses"]["units_30d"], 1)
        [loss] = data["losses"]["recent"]
        self.assertEqual(loss["killmail_id"], 500)
        self.assertEqual(loss["character_name"], "Builder Alt")
        self.assertEqual(
            data["weekly"][-1]["lost"] + data["weekly"][-2]["lost"], 1
        )

    def _loss(self, row_id, moment, system_id):
        EveCharacterKillmail.objects.create(
            id=row_id,
            killmail_id=1000 + row_id,
            killmail_hash="x",
            killmail_time=moment,
            solar_system_id=system_id,
            ship_type_id=SHIP_TYPE_ID,
            victim_character_id=self.main.character_id,
            victim_alliance_id=ALLIANCE_ID,
            attackers="[]",
            items="[]",
            character=self.main,
        )

    def test_losses_cluster_into_fights(self):
        _system(AMAMAKE_ID, "Amamake")
        fight_start = self.now - timedelta(days=7)
        # Four losses an hour apart in Amamake are one fight, even though
        # the first and last are more than the gap apart.
        for i in range(4):
            self._loss(i + 1, fight_start + timedelta(hours=i), AMAMAKE_ID)
        # Back in Amamake the next day: a separate, small fight.
        self._loss(10, fight_start + timedelta(days=1), AMAMAKE_ID)
        # A loss elsewhere in between does not join or split the fight.
        self._loss(11, fight_start + timedelta(minutes=30), HUOLA_ID)

        losses = self._insights()["losses"]

        [fight] = losses["fights"]
        self.assertEqual(fight["solar_system_name"], "Amamake")
        self.assertEqual(fight["units"], 4)
        self.assertEqual(fight["killmail_id"], 1001)
        self.assertEqual(fight["started_at"], fight_start)
        self.assertEqual(fight["ended_at"], fight_start + timedelta(hours=3))
        self.assertEqual(losses["small_fight_units"], 2)
        self.assertEqual(losses["small_fight_systems"], 2)

    def test_non_ships_have_no_hangar_or_loss_tracking(self):
        data = compute_product_insights(self.now)[self.component_product.pk]
        self.assertFalse(data["is_ship"])
        self.assertIsNone(data["hangars"])
        self.assertIsNone(data["losses"])

    def test_cache_miss_queues_one_refresh(self):
        with patch(
            "industry.tasks.refresh_product_insights_task.delay"
        ) as delay:
            self.assertIsNone(product_insights(self.product.pk))
            self.assertIsNone(product_insights(self.product.pk))
        delay.assert_called_once()

    def test_endpoint_serves_cached_insights(self):
        client = Client()
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        url = f"/api/industry/products/{self.product.pk}/insights"

        self.assertEqual(client.get(url).status_code, 401)
        with patch("industry.tasks.refresh_product_insights_task.delay"):
            response = client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready"])

        from industry.tasks import (  # pylint: disable=import-outside-toplevel
            refresh_product_insights_task,
        )

        refresh_product_insights_task()
        data = client.get(url, **headers).json()
        self.assertTrue(data["ready"])
        self.assertTrue(data["is_ship"])
        self.assertEqual(len(data["weekly"]), 13)

        self.assertEqual(
            client.get(
                "/api/industry/products/999999/insights", **headers
            ).status_code,
            404,
        )


class QueueProductInsightsMigrationTestCase(AppTestCase):
    def _queue_refresh(self):
        module = importlib.import_module(
            "industry.migrations.0053_queue_product_insights"
        )
        return module.queue_refresh

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_queues_refresh_on_the_default_queue(self):
        with patch("app.celery.app.send_task") as send_task:
            self._queue_refresh()(None, None)
        send_task.assert_called_once_with(
            "industry.tasks.refresh_product_insights_task", queue="celery"
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_broker_failure_does_not_block_migrate(self):
        with patch(
            "app.celery.app.send_task", side_effect=ConnectionError("down")
        ):
            self._queue_refresh()(None, None)

    def test_skipped_when_celery_runs_inline(self):
        with patch("app.celery.app.send_task") as send_task:
            self._queue_refresh()(None, None)
        send_task.assert_not_called()


class ProductBuildEndpointTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=27, name="Battleship", published=True, eve_category=category
        )
        self.ship = EveType.objects.create(
            id=SHIP_TYPE_ID, name="Test Hull", published=True, eve_group=group
        )
        blueprint = EveType.objects.create(
            id=BLUEPRINT_TYPE_ID,
            name="Test Hull Blueprint",
            published=True,
            eve_group=group,
        )
        component = EveType.objects.create(
            id=COMPONENT_TYPE_ID,
            name="Test Component",
            published=True,
            eve_group=group,
        )
        untracked = EveType.objects.create(
            id=UNTRACKED_TYPE_ID,
            name="Test Mineral",
            published=True,
            eve_group=group,
        )
        EveIndustryActivityProduct.objects.create(
            eve_type=blueprint,
            activity_id=1,
            product_eve_type=self.ship,
            quantity=1,
        )
        EveIndustryActivityDuration.objects.create(
            eve_type=blueprint, activity_id=1, time=7200
        )
        for material, quantity in ((component, 2), (untracked, 100)):
            EveIndustryActivityMaterial.objects.create(
                eve_type=blueprint,
                activity_id=1,
                material_eve_type=material,
                quantity=quantity,
            )
        self.product = IndustryProduct.objects.create(
            eve_type=self.ship, strategy="produced"
        )
        # Saving the hull tracks its inputs too; leave only the component.
        IndustryProduct.objects.filter(eve_type=untracked).delete()
        IndustryProduct.objects.get_or_create(
            eve_type=component, defaults={"strategy": "imported"}
        )
        self.url = f"/api/industry/products/{self.product.pk}/build"

    def test_prices_one_run_and_margin(self):
        for type_id, price in (
            (SHIP_TYPE_ID, 1000),
            (COMPONENT_TYPE_ID, 300),
            (UNTRACKED_TYPE_ID, 2),
        ):
            EveMarketPrice.objects.create(
                eve_type_id=type_id, average_price=price, adjusted_price=price
            )

        data = Client().get(self.url).json()

        self.assertEqual(data["time_seconds"], 7200)
        self.assertEqual(data["activity"], "manufacturing")
        self.assertEqual(data["sell_price"], 1000)
        self.assertEqual(data["material_cost"], 800)
        self.assertEqual(data["margin"], 200)
        self.assertTrue(data["prices_complete"])
        component, mineral = data["materials"]
        self.assertEqual(component["name"], "Test Component")
        self.assertEqual(component["line_cost"], 600)
        self.assertEqual(component["strategy"], "imported")
        self.assertIsNotNone(component["industry_product_id"])
        self.assertIsNone(mineral["strategy"])

    def test_missing_price_leaves_margin_unknown(self):
        EveMarketPrice.objects.create(
            eve_type_id=SHIP_TYPE_ID, average_price=1000, adjusted_price=1000
        )

        data = Client().get(self.url).json()

        self.assertFalse(data["prices_complete"])
        self.assertIsNone(data["margin"])
        self.assertEqual(data["material_cost"], 0)

    def test_unknown_product_and_no_blueprint_are_404(self):
        client = Client()
        self.assertEqual(
            client.get("/api/industry/products/999999/build").status_code, 404
        )
        mineral = IndustryProduct.objects.create(
            eve_type_id=UNTRACKED_TYPE_ID, strategy="harvested"
        )
        self.assertEqual(
            client.get(
                f"/api/industry/products/{mineral.pk}/build"
            ).status_code,
            404,
        )
