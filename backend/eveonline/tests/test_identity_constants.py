"""Shared alliance/faction constants, the corporation scopes and site links."""

from django.test import SimpleTestCase, override_settings

from app.links import PRODUCTION_SITE_URL, site_url
from app.test import TestCase
from eveonline import constants
from eveonline.helpers.alliances import (
    alliance_corporations,
    member_alliance_ids,
    member_corporations,
    tracked_alliance_ids,
)
from eveonline.models import EveAlliance, EveCorporation


class ConstantValuesTestCase(SimpleTestCase):
    """The named constants must keep the values the code used inline."""

    def test_alliance_ids(self):
        self.assertEqual(99011978, constants.MINMATAR_FLEET_ALLIANCE_ID)
        self.assertEqual(
            99012009, constants.MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID
        )
        self.assertEqual(
            frozenset({99011978, 99012009}),
            constants.FL33T_MEMBER_ALLIANCE_IDS,
        )

    def test_holding_corporation_ticker(self):
        self.assertEqual("MH0LD", constants.HOLDING_CORPORATION_TICKER)

    def test_faction_ids(self):
        self.assertEqual(500001, constants.CALDARI_FACTION_ID)
        self.assertEqual(500002, constants.MINMATAR_FACTION_ID)
        self.assertEqual(500003, constants.AMARR_FACTION_ID)
        self.assertEqual(500004, constants.GALLENTE_FACTION_ID)

    def test_production_site_url(self):
        self.assertEqual("https://my.minmatar.org", PRODUCTION_SITE_URL)


class SiteUrlTestCase(SimpleTestCase):
    @override_settings(WEB_LINK_URL="https://my.minmatar.org")
    def test_production_base(self):
        self.assertEqual("https://my.minmatar.org", site_url())
        self.assertEqual("https://my.minmatar.org/", site_url("/"))
        self.assertEqual(
            "https://my.minmatar.org/fleets/history/7",
            site_url("/fleets/history/7"),
        )

    @override_settings(WEB_LINK_URL="http://localhost:4321/")
    def test_follows_setting_and_trims_slashes(self):
        self.assertEqual("http://localhost:4321", site_url())
        self.assertEqual(
            "http://localhost:4321/learning/", site_url("learning/")
        )


class CorporationScopesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        fl33t = EveAlliance.objects.create(
            alliance_id=constants.MINMATAR_FLEET_ALLIANCE_ID,
            name="Minmatar Fleet Alliance",
        )
        build = EveAlliance.objects.create(
            alliance_id=constants.MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
            name="Minmatar Fleet Associates",
        )
        other = EveAlliance.objects.create(
            alliance_id=99000001, name="Some Friends"
        )
        EveCorporation.objects.create(
            corporation_id=1, name="Line Corp", ticker="LINE", alliance=fl33t
        )
        EveCorporation.objects.create(
            corporation_id=2, name="Holding", ticker="MH0LD", alliance=fl33t
        )
        EveCorporation.objects.create(
            corporation_id=3, name="Builders", ticker="BLD", alliance=build
        )
        EveCorporation.objects.create(
            corporation_id=4, name="Friends", ticker="FRND", alliance=other
        )
        EveCorporation.objects.create(
            corporation_id=5, name="Outsiders", ticker="OUT"
        )

    @staticmethod
    def _ids(queryset):
        return set(queryset.values_list("corporation_id", flat=True))

    def test_member_corporations_are_fl33t_and_build(self):
        self.assertEqual({1, 2, 3}, self._ids(member_corporations()))

    def test_alliance_corporations(self):
        self.assertEqual({1, 2}, self._ids(alliance_corporations()))
        self.assertEqual(
            {1},
            self._ids(
                alliance_corporations(include_holding_corporation=False)
            ),
        )

    def test_member_scope_ignores_alliance_names(self):
        EveAlliance.objects.filter(
            alliance_id=constants.MINMATAR_FLEET_ALLIANCE_ID
        ).update(name="Renamed In Game")
        self.assertEqual({1, 2, 3}, self._ids(member_corporations()))

    def test_tracked_covers_member_alliances(self):
        tracked = tracked_alliance_ids()
        self.assertEqual({99011978, 99012009, 99000001}, tracked)
        self.assertLessEqual(set(member_alliance_ids()), tracked)
