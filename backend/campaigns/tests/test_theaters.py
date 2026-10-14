"""FW objective flag and ops areas on the wire."""

from django.test import TestCase

from campaigns.endpoints import serializers
from campaigns.forms import (
    CampaignConstellationTheaterForm,
    CampaignRegionTheaterForm,
    CampaignSystemTheaterForm,
)
from campaigns.models import (
    AreaScope,
    CampaignArea,
    CampaignKind,
    SystemGoal,
    SystemPriority,
)
from campaigns.tests.helpers import make_campaign
from eveuniverse.models import EveConstellation, EveRegion, EveSolarSystem


def _ensure_map():
    region, _ = EveRegion.objects.get_or_create(
        id=10000036, defaults={"name": "Devoid"}
    )
    constellation, _ = EveConstellation.objects.get_or_create(
        id=20000372,
        defaults={"name": "Hed", "eve_region": region},
    )
    system, _ = EveSolarSystem.objects.get_or_create(
        id=30002537,
        defaults={
            "name": "Amamake",
            "eve_constellation": constellation,
            "security_status": -0.4,
        },
    )
    return system, constellation, region


class TheaterSerializationTests(TestCase):
    def test_system_summary_includes_is_fw_objective(self):
        campaign = make_campaign()
        system = campaign.systems.first()
        summary = serializers.system_summary(system, with_trend=False)
        self.assertTrue(summary["is_fw_objective"])

        system.is_fw_objective = False
        system.goal = SystemGoal.NONE
        system.save(update_fields=["is_fw_objective", "goal"])
        summary = serializers.system_summary(system, with_trend=False)
        self.assertFalse(summary["is_fw_objective"])

    def test_campaign_list_includes_areas(self):
        campaign = make_campaign(
            kind=CampaignKind.STRATEGIC, slug="area-list", short_code="ARL"
        )
        CampaignArea.objects.create(
            campaign=campaign,
            scope=AreaScope.REGION,
            region_id=10000036,
            name="Devoid",
            goal=SystemGoal.RECON,
            priority=SystemPriority.HIGH,
        )
        item = serializers.list_item(campaign, user=None)
        self.assertEqual(len(item["areas"]), 1)
        self.assertEqual(item["areas"][0]["name"], "Devoid")
        self.assertEqual(item["areas"][0]["scope"], "region")
        self.assertEqual(item["areas"][0]["region_id"], 10000036)
        self.assertEqual(item["areas"][0]["goal"], "recon")
        self.assertEqual(item["areas"][0]["priority"], "high")


class TheaterFormTests(TestCase):
    def setUp(self):
        self.system, self.constellation, self.region = _ensure_map()

    def test_system_form_resolves_lookup(self):
        campaign = make_campaign(slug="form-sys", short_code="FSY")
        form = CampaignSystemTheaterForm(
            data={
                "eve_solar_system": self.system.id,
                "goal": SystemGoal.RECON,
                "priority": SystemPriority.MEDIUM,
                "is_fw_objective": False,
            }
        )
        form.instance.campaign = campaign
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.name, "Amamake")
        self.assertEqual(instance.solar_system_id, 30002537)
        self.assertEqual(instance.role, "secondary")

    def test_constellation_form_sets_scope_and_goal(self):
        campaign = make_campaign(slug="form-area", short_code="FAR")
        form = CampaignConstellationTheaterForm(
            data={
                "eve_constellation": self.constellation.id,
                "goal": SystemGoal.HOLD,
                "priority": SystemPriority.HIGH,
            }
        )
        form.instance.campaign = campaign
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.scope, AreaScope.CONSTELLATION)
        self.assertEqual(instance.constellation_id, 20000372)
        self.assertEqual(instance.name, "Hed")
        self.assertEqual(instance.goal, SystemGoal.HOLD)
        self.assertIsNone(instance.region_id)

    def test_region_form_sets_scope_and_goal(self):
        campaign = make_campaign(slug="form-region", short_code="FRG")
        form = CampaignRegionTheaterForm(
            data={
                "eve_region": self.region.id,
                "goal": SystemGoal.RECON,
                "priority": SystemPriority.LOW,
            }
        )
        form.instance.campaign = campaign
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.scope, AreaScope.REGION)
        self.assertEqual(instance.region_id, 10000036)
        self.assertEqual(instance.goal, SystemGoal.RECON)
        self.assertIsNone(instance.constellation_id)
