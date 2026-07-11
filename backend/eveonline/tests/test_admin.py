"""Tests for eveonline admin customizations."""

from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import RequestFactory

from discord.models import DiscordUser
from eveonline.admin import (
    EveCharacterAdmin,
    EveCharacterAllianceFilter,
    EveCharacterCorporationFilter,
)
from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterTag,
    EveCorporation,
    EvePlayer,
)

from app.test import TestCase


class EveCharacterAdminTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        signals.post_save.disconnect(
            sender=EveAlliance,
            dispatch_uid="eve_alliance_post_save",
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.model_admin = EveCharacterAdmin(EveCharacter, admin.site)

        self.alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Minmatar Fleet Alliance",
            ticker="FL33T",
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98002222,
            name="Test Corp",
            ticker="TCOR",
            alliance=self.alliance,
        )

        self.user = User.objects.create_user(
            username="pilotuser",
            password="password",
        )
        self.primary = EveCharacter.objects.create(
            character_id=100001,
            character_name="Primary Pilot",
            corporation_id=self.corporation.corporation_id,
            alliance_id=self.alliance.alliance_id,
            user=self.user,
        )
        self.alt = EveCharacter.objects.create(
            character_id=100002,
            character_name="Alt Pilot",
            corporation_id=self.corporation.corporation_id,
            alliance_id=self.alliance.alliance_id,
            user=self.user,
        )
        EvePlayer.objects.create(
            nickname="pilotuser",
            user=self.user,
            primary_character=self.primary,
        )
        set_primary_character(self.user, self.primary)
        DiscordUser.objects.create(
            id=900001,
            discord_tag="pilot#1234",
            nickname="DiscordPilot",
            user=self.user,
        )
        self.unlinked = EveCharacter.objects.create(
            character_id=100003,
            character_name="Unlinked Pilot",
        )

        self.other_alliance = EveAlliance.objects.create(
            alliance_id=99009999,
            name="Other Alliance",
            ticker="OTHR",
        )
        self.other_corporation = EveCorporation.objects.create(
            corporation_id=98009999,
            name="Other Corp",
            ticker="OCOR",
            alliance=self.other_alliance,
        )
        EveCharacter.objects.create(
            character_id=100004,
            character_name="Other Corp Pilot",
            corporation_id=self.other_corporation.corporation_id,
            alliance_id=self.other_alliance.alliance_id,
        )

    def _request(self, query_string=""):
        request = self.factory.get(
            f"/admin/eveonline/evecharacter/{query_string}"
        )
        request.user = self.admin_user
        return request

    def test_list_per_page(self):
        self.assertEqual(self.model_admin.list_per_page, 50)

    def test_search_fields_include_related_paths(self):
        self.assertIn(
            "user__eveplayer__primary_character__character_name",
            self.model_admin.search_fields,
        )
        self.assertIn(
            "user__discord_user__discord_tag",
            self.model_admin.search_fields,
        )
        self.assertIn(
            "user__discord_user__nickname",
            self.model_admin.search_fields,
        )

    def test_corporation_filter_lookups_use_names(self):
        request = self._request()
        filter_instance = EveCharacterCorporationFilter(
            request,
            {},
            EveCharacter,
            self.model_admin,
        )
        lookups = dict(filter_instance.lookups(request, self.model_admin))
        self.assertIn(self.corporation.corporation_id, lookups)
        self.assertEqual(
            lookups[self.corporation.corporation_id], "Test Corp (TCOR)"
        )

    def test_alliance_filter_lookups_use_names(self):
        request = self._request()
        filter_instance = EveCharacterAllianceFilter(
            request,
            {},
            EveCharacter,
            self.model_admin,
        )
        lookups = dict(filter_instance.lookups(request, self.model_admin))
        self.assertIn(self.alliance.alliance_id, lookups)
        self.assertEqual(
            lookups[self.alliance.alliance_id],
            "Minmatar Fleet Alliance (FL33T)",
        )

    def test_corporation_filter_excludes_non_alliance_corps(self):
        request = self._request()
        filter_instance = EveCharacterCorporationFilter(
            request,
            {},
            EveCharacter,
            self.model_admin,
        )
        lookups = dict(filter_instance.lookups(request, self.model_admin))
        self.assertNotIn(self.other_corporation.corporation_id, lookups)

    def test_alliance_filter_excludes_non_minmatar_fleet_alliances(self):
        request = self._request()
        filter_instance = EveCharacterAllianceFilter(
            request,
            {},
            EveCharacter,
            self.model_admin,
        )
        lookups = dict(filter_instance.lookups(request, self.model_admin))
        self.assertNotIn(self.other_alliance.alliance_id, lookups)

    def test_changelist_search_by_discord_tag(self):
        request = self._request("?q=pilot%231234")
        changelist = self.model_admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertIn(self.primary, queryset)
        self.assertIn(self.alt, queryset)
        self.assertNotIn(self.unlinked, queryset)

    def test_changelist_search_by_primary_character_name(self):
        request = self._request("?q=Primary+Pilot")
        changelist = self.model_admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertIn(self.primary, queryset)
        self.assertIn(self.alt, queryset)
        self.assertNotIn(self.unlinked, queryset)

    def test_character_tag_inline_present(self):
        inline_models = [inline.model for inline in self.model_admin.inlines]
        self.assertIn(EveCharacterTag, inline_models)
