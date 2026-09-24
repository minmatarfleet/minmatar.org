"""Campaign kinds, opponents, and structure theaters."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import (
    CampaignKind,
    CampaignOpponent,
    CampaignStructure,
    StructureSource,
    StructureStatus,
)
from campaigns.services import structures as structure_service
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tests.helpers import (
    KAMELA,
    auth_headers,
    enlist,
    make_campaign,
    make_feed_killmail,
)
from eveonline.models import EveAlliance, EveCorporation
from feed.models import FeedMonitoredSystem

FORTIZAR_TYPE_ID = 35833


class CampaignKindTests(TestCase):
    def test_new_campaigns_default_to_faction_warfare(self):
        campaign = make_campaign()
        self.assertEqual(campaign.kind, CampaignKind.FACTION_WARFARE)

    def test_strategic_campaign_can_skip_systems_at_create(self):
        campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            slug="cva-war",
            short_code="CVA",
        )
        campaign.systems.all().delete()
        CampaignOpponent.objects.create(
            campaign=campaign,
            name="Curatores Veritatis Alliance",
            ticker="CVA",
            alliance_id=1354830081,
        )
        self.assertTrue(campaign.is_strategic)
        self.assertEqual(campaign.opponents.count(), 1)


class StructureAttachTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            slug="cva-push",
            short_code="CVP",
        )
        # Start without systems so attach grows the theater.
        self.campaign.systems.all().delete()
        FeedMonitoredSystem.objects.filter(solar_system_id=KAMELA).delete()

    def test_attach_structure_adds_system_and_feed_monitor(self):
        FeedMonitoredSystem.objects.create(
            solar_system_id=KAMELA,
            name="Kamela",
            source=FeedMonitoredSystem.Source.FW_WARZONE,
            is_active=True,
        )
        structure = structure_service.attach_structure(
            self.campaign,
            name="WATERMELLON",
            structure_type="fortizar",
            system_name="Kamela",
            solar_system_id=KAMELA,
            alliance_name="Curatores Veritatis Alliance",
            alliance_id=1354830081,
        )

        self.assertEqual(structure.status, StructureStatus.ANCHORED)
        self.assertEqual(structure.type_id, FORTIZAR_TYPE_ID)
        system = self.campaign.systems.get(solar_system_id=KAMELA)
        self.assertFalse(system.is_fw_objective)
        monitored = FeedMonitoredSystem.objects.get(solar_system_id=KAMELA)
        self.assertTrue(monitored.is_active)

    def test_attach_structure_stores_fitting_and_reinforce_hour(self):
        FeedMonitoredSystem.objects.create(
            solar_system_id=KAMELA,
            name="Kamela",
            source=FeedMonitoredSystem.Source.FW_WARZONE,
            is_active=True,
        )
        fit = "[Fortizar, WATERMELLON]\nStandup Ballistic Control System I"
        structure = structure_service.attach_structure(
            self.campaign,
            name="WATERMELLON",
            structure_type="fortizar",
            system_name="Kamela",
            solar_system_id=KAMELA,
            fitting=fit,
            reinforce_hour=18,
        )

        self.assertEqual(structure.fitting, fit)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(structure.source, StructureSource.RECON)

    def test_attach_structure_resolves_owner_and_related_alliance(self):
        FeedMonitoredSystem.objects.create(
            solar_system_id=KAMELA,
            name="Kamela",
            source=FeedMonitoredSystem.Source.FW_WARZONE,
            is_active=True,
        )
        cva = EveAlliance.objects.create(
            alliance_id=1354830081,
            name="Curatores Veritatis Alliance",
            ticker="CVA",
        )
        alt = EveCorporation.objects.create(
            corporation_id=98451147,
            name="CVA Logistics Alts",
            alliance=cva,
        )
        structure = structure_service.attach_structure(
            self.campaign,
            name="WATERMELLON",
            structure_type="fortizar",
            system_name="Kamela",
            solar_system_id=KAMELA,
            corporation_name=alt.name,
            related_alliance_name="Curatores Veritatis Alliance",
        )

        self.assertEqual(structure.corporation_id, alt.corporation_id)
        self.assertEqual(structure.corporation_name, alt.name)
        self.assertEqual(structure.alliance_id, cva.alliance_id)
        self.assertEqual(structure.related_alliance_id, cva.alliance_id)
        self.assertEqual(
            structure.related_alliance_name, "Curatores Veritatis Alliance"
        )

    def test_attach_structure_rejects_invalid_reinforce_hour(self):
        with self.assertRaises(ValueError):
            structure_service.attach_structure(
                self.campaign,
                name="WATERMELLON",
                structure_type="fortizar",
                system_name="Kamela",
                solar_system_id=KAMELA,
                reinforce_hour=24,
            )

    def test_structure_killmail_is_flagged_and_marks_recon(self):
        structure_service.attach_structure(
            self.campaign,
            name="WATERMELLON",
            structure_type="fortizar",
            system_name="Kamela",
            solar_system_id=KAMELA,
        )
        FeedMonitoredSystem.objects.get_or_create(
            solar_system_id=KAMELA,
            defaults={
                "name": "Kamela",
                "source": FeedMonitoredSystem.Source.CAMPAIGN,
                "is_active": True,
            },
        )
        character = enlist(self.campaign, "fc", 9001)[1]

        mail = make_feed_killmail(
            killmail_id=42,
            solar_system_id=KAMELA,
            victim_character_id=None,
            ship_type_id=FORTIZAR_TYPE_ID,
            attacker_ids=[character.character_id],
        )

        attributed = attribute_feed_killmail(mail)
        self.assertEqual(attributed, 1)

        campaign_mail = self.campaign.killmails.get(killmail_id=42)
        self.assertTrue(campaign_mail.is_structure)
        self.assertFalse(campaign_mail.is_capital)
        self.assertEqual(campaign_mail.outcome, "kill")

        recon = CampaignStructure.objects.get(campaign=self.campaign)
        self.assertEqual(recon.status, StructureStatus.DESTROYED)
        self.assertEqual(recon.source, StructureSource.KILLMAIL)

    def test_is_structure_type_catalog(self):
        self.assertTrue(structure_service.is_structure_type(FORTIZAR_TYPE_ID))
        self.assertFalse(structure_service.is_structure_type(22468))


class StructureScoutApiTests(TestCase):
    """POST /api/campaigns/{slug}/structures scout reports."""

    def setUp(self):
        self.client = Client()
        self.auth_headers = auth_headers
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            slug="cva-recon",
            short_code="CVR",
        )
        FeedMonitoredSystem.objects.get_or_create(
            solar_system_id=KAMELA,
            defaults={
                "name": "Kamela",
                "source": FeedMonitoredSystem.Source.FW_WARZONE,
                "is_active": True,
            },
        )
        self.staff = User.objects.create(
            username="scout-staff", is_superuser=True
        )

    def test_scout_report_stores_fitting_and_reinforce_hour(self):
        fit = "[Fortizar, WATERMELLON]\nStandup Ballistic Control System I"
        response = self.client.post(
            f"/api/campaigns/{self.campaign.slug}/structures",
            data={
                "name": "WATERMELLON",
                "structure_type": "fortizar",
                "system_name": "Kamela",
                "corporation_name": "CVA Logistics",
                "alliance_name": "Curatores Veritatis Alliance",
                "fitting": fit,
                "reinforce_hour": 18,
            },
            content_type="application/json",
            **self.auth_headers(self.staff),
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["fitting"], fit)
        self.assertEqual(body["reinforce_hour"], 18)
        self.assertEqual(body["status"], "anchored")
        self.assertEqual(body["source"], "recon")

        recon = CampaignStructure.objects.get(campaign=self.campaign)
        self.assertEqual(recon.fitting, fit)
        self.assertEqual(recon.reinforce_hour, 18)

    def test_scout_report_with_timer_creates_reinforced_row(self):
        timer_at = (timezone.now() + timedelta(hours=12)).isoformat()
        response = self.client.post(
            f"/api/campaigns/{self.campaign.slug}/structures",
            data={
                "name": "WATERMELLON",
                "structure_type": "fortizar",
                "system_name": "Kamela",
                "fitting": "Standup Multirole Missile Launcher I",
                "reinforce_hour": 18,
                "timer_at": timer_at,
                "timer_state": "armor",
            },
            content_type="application/json",
            **self.auth_headers(self.staff),
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["status"], "reinforced")
        self.assertEqual(body["source"], "timer")
        self.assertIsNotNone(body["timer_id"])
        self.assertEqual(
            body["fitting"], "Standup Multirole Missile Launcher I"
        )
        self.assertEqual(body["reinforce_hour"], 18)
