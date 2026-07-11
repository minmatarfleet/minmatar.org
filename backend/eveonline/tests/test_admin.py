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


class AdminAppListGroupingTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )

    def _model_names(self, app_list, section_name):
        section = next(app for app in app_list if app["name"] == section_name)
        return {model["object_name"].lower() for model in section["models"]}

    def _section_names(self, app_list):
        return [app["name"] for app in app_list]

    def test_audit_entries_under_system_not_community(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        system_models = self._model_names(app_list, "System")
        community_models = self._model_names(app_list, "Community")

        self.assertIn("auditentry", system_models)
        self.assertNotIn("auditentry", community_models)

    def test_mumble_access_under_system_not_community(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        system_models = self._model_names(app_list, "System")
        community_models = self._model_names(app_list, "Community")

        self.assertIn("mumbleaccess", system_models)
        self.assertNotIn("mumbleaccess", community_models)

    def test_fleets_under_alliance_not_standalone(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        alliance_models = self._model_names(app_list, "Alliance")
        section_names = self._section_names(app_list)

        self.assertIn("evefleet", alliance_models)
        self.assertIn("evefleetaudience", alliance_models)
        self.assertNotIn("fleets", section_names)

    def test_readiness_and_supply_follow_staging_systems(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)
        section_names = self._section_names(app_list)

        self.assertLess(
            section_names.index("Staging Systems"),
            section_names.index("Readiness"),
        )
        self.assertLess(
            section_names.index("Readiness"),
            section_names.index("Supply"),
        )
        self.assertLess(
            section_names.index("Supply"),
            section_names.index("Characters"),
        )

    def test_fleet_instances_hidden_from_alliance(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        alliance_models = self._model_names(app_list, "Alliance")

        self.assertIn("evefleet", alliance_models)
        self.assertNotIn("evefleetinstance", alliance_models)
        self.assertNotIn("evefleetinstancemember", alliance_models)
        self.assertNotIn("evefleetshipreimbursement", alliance_models)

    def test_srp_reimbursements_hidden_from_alliance(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        alliance_models = self._model_names(app_list, "Alliance")

        self.assertIn("shipreimbursementprogram", alliance_models)
        self.assertNotIn("evefleetshipreimbursement", alliance_models)

    def test_experimental_section_at_bottom(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)
        section_names = self._section_names(app_list)

        self.assertIn("Experimental", section_names)
        self.assertLess(
            section_names.index("System"),
            section_names.index("Experimental"),
        )

        experimental_models = self._model_names(app_list, "Experimental")
        experimental_names = self._display_names(app_list, "Experimental")
        self.assertIn("eveaccesslist", experimental_models)
        self.assertIn("industryproduct", experimental_models)
        self.assertIn("miningupgradecompletion", experimental_models)
        self.assertIn("systemsovereigntyconfig", experimental_models)
        self.assertIn("products", experimental_names)
        self.assertIn("mining completions", experimental_names)
        self.assertNotIn("eveaccesslistmember", experimental_models)

    def test_hidden_models_not_in_sidebar(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        all_models = set()
        for section in app_list:
            all_models.update(self._model_names(app_list, section["name"]))

        self.assertNotIn("evepost", all_models)
        self.assertNotIn("evepostimage", all_models)
        self.assertNotIn("evecorporationcontract", all_models)
        self.assertNotIn("evecorporationindustryjob", all_models)
        self.assertNotIn("evefleetshipreimbursement", all_models)
        self.assertNotIn("industryorderitem", all_models)
        self.assertNotIn("industryorderitemassignment", all_models)

    def _display_names(self, app_list, section_name):
        section = next(app for app in app_list if app["name"] == section_name)
        return {model["name"].lower() for model in section["models"]}

    def test_supply_shows_industry_orders_hub_only(self):
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        app_list = admin.site.get_app_list(request)

        supply_objects = self._model_names(app_list, "Supply")
        supply_names = self._display_names(app_list, "Supply")
        self.assertIn("industry orders", supply_names)
        self.assertNotIn("industryorder", supply_objects)
        self.assertNotIn("industryproduct", supply_objects)
        self.assertNotIn("miningupgradecompletion", supply_objects)
