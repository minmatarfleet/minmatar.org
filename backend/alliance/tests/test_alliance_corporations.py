"""Which corporations alliance health and officer access cover."""

from django.contrib.auth.models import User

from alliance.helpers.access import mfa_corporation_qs, officer_corp_ids
from alliance.helpers.health import compute_alliance_health
from app.test import TestCase
from eveonline.constants import (
    MINMATAR_FLEET_ALLIANCE_ID,
    MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
)
from eveonline.models import EveAlliance, EveCharacter, EveCorporation


class AllianceCorporationScopeTestCase(TestCase):
    def setUp(self):
        super().setUp()
        fl33t = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
            name="Minmatar Fleet Alliance",
        )
        build = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
            name="Minmatar Fleet Associates",
        )
        self.line = EveCorporation.objects.create(
            corporation_id=2001, name="Line", ticker="LINE", alliance=fl33t
        )
        self.holding = EveCorporation.objects.create(
            corporation_id=2002,
            name="Holding",
            ticker="MH0LD",
            alliance=fl33t,
        )
        self.associate = EveCorporation.objects.create(
            corporation_id=2003, name="Build", ticker="BLD", alliance=build
        )
        self.officer = User.objects.create_user(username="officer")
        for corp in (self.line, self.holding, self.associate):
            corp.directors.add(
                EveCharacter.objects.create(
                    character_id=corp.corporation_id + 90000000,
                    character_name=f"Director {corp.ticker}",
                    corporation_id=corp.corporation_id,
                    user=self.officer,
                )
            )

    def test_mfa_corporations_exclude_holding_and_associates(self):
        self.assertEqual(
            {2001},
            set(mfa_corporation_qs().values_list("corporation_id", flat=True)),
        )

    def test_officer_access_skips_holding_corporation(self):
        self.assertEqual({2001}, officer_corp_ids(self.officer))

    def test_health_corporation_list_skips_holding_corporation(self):
        payload = compute_alliance_health()
        self.assertEqual(
            [2001],
            [row["corporation_id"] for row in payload["corporations"]],
        )
