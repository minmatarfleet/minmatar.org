"""The campaign timerboard and its reinforcement stages."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import CampaignKind, CampaignStructure
from campaigns.services.timers import TIMER_STAGES, timer_stage
from campaigns.tests.helpers import KAMELA, auth_headers, grant, make_campaign
from structures.models import EveStructureTimer


class TimerStageTestCase(TestCase):
    def test_one_reinforcement_types_are_always_final(self):
        for structure_type in (
            "astrahus",
            "raitaru",
            "athanor",
            "orbital_skyhook",
            "metenox_moon_drill",
            "player_owned_customs_office",
            "player_owned_starbase",
        ):
            self.assertEqual(timer_stage(structure_type, "armor"), (3, True))
            self.assertEqual(timer_stage(structure_type, "hull"), (3, True))

    def test_two_reinforcement_types_have_an_armor_stage(self):
        for structure_type in (
            "fortizar",
            "azbel",
            "tatara",
            "keepstar",
            "sotiyo",
            "ansiblex_jump_gate",
            "pharolux_cyno_beacon",
            "tenebrex_cyno_jammer",
        ):
            self.assertEqual(timer_stage(structure_type, "armor"), (2, False))
            self.assertEqual(timer_stage(structure_type, "hull"), (3, True))

    def test_every_structure_type_has_a_stage(self):
        types = {key for key, _ in CampaignStructure.TYPE_CHOICES}
        self.assertEqual(types, set(TIMER_STAGES))

    def test_anchoring_is_not_a_kill(self):
        self.assertEqual(timer_stage("astrahus", "anchoring"), (1, False))


class TimerboardApiTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        self.viewer = User.objects.create(username="viewer")
        grant(self.viewer, "view_campaign")
        now = timezone.now()

        def timer(name, structure_type, state, hours, **fields):
            return EveStructureTimer.objects.create(
                name=name,
                type=structure_type,
                state=state,
                timer=now + timedelta(hours=hours),
                system_name="Kamela",
                **fields,
            )

        timer("Later Box", "astrahus", "armor", 20, campaign=self.campaign)
        timer("Big Box", "fortizar", "armor", 5, campaign=self.campaign)
        linked = timer("Dead Box", "raitaru", "armor", -30)
        timer("Other Campaign", "astrahus", "armor", 2)
        CampaignStructure.objects.create(
            campaign=self.campaign,
            name="Dead Box",
            structure_type="raitaru",
            solar_system_id=KAMELA,
            system_name="Kamela",
            status="destroyed",
            timer=linked,
        )

    def test_upcoming_soonest_first_then_done(self):
        response = Client().get(
            f"/api/campaigns/{self.campaign.slug}/timers",
            **auth_headers(self.viewer),
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(
            [row["name"] for row in rows],
            ["Big Box", "Later Box", "Dead Box"],
        )
        big, later, dead = rows
        self.assertEqual((big["stage"], big["final"]), (2, False))
        self.assertEqual((later["stage"], later["final"]), (3, True))
        self.assertTrue(dead["done"])
        self.assertEqual(dead["outcome"], "destroyed")
        self.assertEqual(big["type_name"], "Fortizar")
