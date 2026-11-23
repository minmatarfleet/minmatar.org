"""Create, rename and archive tribes and groups from the site (#3002)."""

import json
from unittest.mock import patch

import requests
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase

from audit.models import AuditEntry
from discord.models import DiscordRole
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncFeatures,
)
from tribes.helpers.structure import can_manage_structure
from tribes.models import Tribe, TribeGroup
from tribes.tests.test_chief_volunteers import (  # noqa: F401  # pylint: disable=unused-import
    _auth,
    _pilot,
    setUpModule,
)

BASE_URL = "/api/tribes"


class StructureTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.people_team = Group.objects.create(name="People Team")
        clear_feature_cache()
        SyncFeatures().handle()
        clear_feature_cache()
        self.manager = _pilot("people", 93001, "People Pilot")
        self.manager.groups.add(self.people_team)
        self.pilot = _pilot("plain", 93002, "Plain Pilot")
        self.tribe = Tribe.objects.create(
            name="Supply",
            slug="supply-structure",
            group=Group.objects.create(name="Supply"),
        )
        clear_feature_cache()

    def _send(self, method, url, user, body):
        return getattr(self.client, method)(
            f"{BASE_URL}{url}",
            data=json.dumps(body),
            content_type="application/json",
            **(_auth(user) if user else {}),
        )

    # Access

    def test_people_team_superusers_and_the_admin_permission_manage(self):
        self.assertTrue(can_manage_structure(self.manager))
        self.assertFalse(can_manage_structure(self.pilot))
        admin = _pilot("root", 93003, "Root")
        admin.is_superuser = True
        admin.save()
        self.assertTrue(can_manage_structure(admin))
        editor = _pilot("editor", 93004, "Admin Editor")
        editor.user_permissions.add(
            Permission.objects.get(codename="change_tribe")
        )
        self.assertTrue(can_manage_structure(editor))

    def test_plain_pilots_and_anonymous_are_refused(self):
        for user, status in ((self.pilot, 403), (None, 401)):
            with self.subTest(user=user):
                self.assertEqual(
                    self._send(
                        "post", "/", user, {"name": "Nope"}
                    ).status_code,
                    status,
                )
                self.assertEqual(
                    self._send(
                        "patch", f"/{self.tribe.pk}", user, {"name": "Nope"}
                    ).status_code,
                    status,
                )
                self.assertEqual(
                    self._send(
                        "post",
                        f"/{self.tribe.pk}/groups",
                        user,
                        {"name": "Nope"},
                    ).status_code,
                    status,
                )
        self.assertFalse(Tribe.objects.filter(name="Nope").exists())
        self.assertFalse(Group.objects.filter(name="Nope").exists())

    # Create

    def test_create_a_tribe_makes_its_auth_group(self):
        response = self._send(
            "post",
            "/",
            self.manager,
            {"name": "  Black   Ops ", "description": "Covert work"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["name"], "Black Ops")
        self.assertEqual(body["slug"], "black-ops")
        self.assertTrue(body["can_set_chief"])
        tribe = Tribe.objects.get(pk=body["id"])
        self.assertEqual(tribe.group.name, "Black Ops")
        self.assertEqual(tribe.description, "Covert work")
        self.assertTrue(
            AuditEntry.objects.filter(
                user=self.manager, summary="Created tribe Black Ops"
            ).exists()
        )

    def test_create_a_tribe_refuses_taken_slugs_and_names(self):
        taken_slug = self._send(
            "post",
            "/",
            self.manager,
            {"name": "Other", "slug": "supply-structure"},
        )
        self.assertEqual(taken_slug.status_code, 400)
        Group.objects.create(name="Capitals")
        taken_role = self._send(
            "post", "/", self.manager, {"name": "Capitals"}
        )
        self.assertEqual(taken_role.status_code, 400)
        self.assertIn("already exists", taken_role.json()["detail"])
        empty = self._send("post", "/", self.manager, {"name": "   "})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(Tribe.objects.count(), 1)

    def test_create_a_group_makes_its_auth_group_and_code(self):
        response = self._send(
            "post",
            f"/{self.tribe.pk}/groups",
            self.manager,
            {"name": "Haulers"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        group = TribeGroup.objects.get(pk=response.json()["id"])
        self.assertEqual(group.code, "supply-structure.haulers")
        self.assertEqual(group.group.name, "Haulers")
        self.assertTrue(group.is_active)
        again = self._send(
            "post",
            f"/{self.tribe.pk}/groups",
            self.manager,
            {"name": "haulers"},
        )
        self.assertEqual(again.status_code, 400)

    def test_no_groups_in_an_archived_tribe(self):
        self.tribe.is_active = False
        self.tribe.save()
        response = self._send(
            "post", f"/{self.tribe.pk}/groups", self.manager, {"name": "Late"}
        )
        self.assertEqual(response.status_code, 400)

    def test_a_discord_failure_creates_nothing(self):
        def group_then_discord_fails(**fields):
            # The group row is written, then the Discord role call fails
            # (what group_post_save does when Discord is down).
            Group(**fields).save()
            raise requests.HTTPError("discord down")

        with patch(
            "tribes.helpers.structure.Group.objects.create",
            side_effect=group_then_discord_fails,
        ):
            response = self._send("post", "/", self.manager, {"name": "Lost"})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(Tribe.objects.filter(name="Lost").exists())
        self.assertFalse(Group.objects.filter(name="Lost").exists())

    # Rename

    def test_rename_a_tribe_renames_its_group_and_discord_role(self):
        DiscordRole.objects.create(
            role_id=555, name="Supply", group=self.tribe.group
        )
        with patch("tribes.helpers.structure.DiscordClient") as client:
            response = self._send(
                "patch",
                f"/{self.tribe.pk}",
                self.manager,
                {"name": "Logistics Supply"},
            )
        self.assertEqual(response.status_code, 200, response.content)
        client.return_value.edit_role.assert_called_once_with(
            555, "Logistics Supply"
        )
        self.tribe.refresh_from_db()
        self.assertEqual(self.tribe.name, "Logistics Supply")
        self.assertEqual(self.tribe.slug, "supply-structure")
        self.assertEqual(self.tribe.group.name, "Logistics Supply")
        self.assertEqual(
            DiscordRole.objects.get(role_id=555).name, "Logistics Supply"
        )

    def test_a_failed_discord_rename_changes_nothing(self):
        DiscordRole.objects.create(
            role_id=556, name="Supply", group=self.tribe.group
        )
        with patch("tribes.helpers.structure.DiscordClient") as client:
            client.return_value.edit_role.side_effect = requests.HTTPError(
                "403"
            )
            response = self._send(
                "patch", f"/{self.tribe.pk}", self.manager, {"name": "Nope"}
            )
        self.assertEqual(response.status_code, 502)
        self.tribe.refresh_from_db()
        self.assertEqual(self.tribe.name, "Supply")
        self.assertEqual(self.tribe.group.name, "Supply")

    def test_rename_a_group_keeps_its_code(self):
        group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Miners",
            code="supply-structure.miners",
            group=Group.objects.create(name="Miners"),
        )
        response = self._send(
            "patch",
            f"/{self.tribe.pk}/groups/{group.pk}",
            self.manager,
            {"name": "Ore Miners"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        group.refresh_from_db()
        self.assertEqual(group.name, "Ore Miners")
        self.assertEqual(group.code, "supply-structure.miners")
        self.assertEqual(group.group.name, "Ore Miners")

    # Archive

    def test_archive_and_restore_a_tribe(self):
        archived = self._send(
            "patch", f"/{self.tribe.pk}", self.manager, {"is_active": False}
        )
        self.assertEqual(archived.status_code, 200)
        self.assertFalse(archived.json()["is_active"])
        listed = [t["id"] for t in self.client.get(f"{BASE_URL}/").json()]
        self.assertNotIn(self.tribe.pk, listed)
        restored = self._send(
            "patch", f"/{self.tribe.pk}", self.manager, {"is_active": True}
        )
        self.assertTrue(restored.json()["is_active"])
        self.assertTrue(
            AuditEntry.objects.filter(
                summary="Tribe Supply: archived"
            ).exists()
        )

    def test_archived_lists_are_for_managers_only(self):
        self.tribe.is_active = False
        self.tribe.save()
        TribeGroup.objects.create(
            tribe=self.tribe,
            name="Old",
            code="supply-structure.old",
            is_active=False,
        )
        url = f"{BASE_URL}/?archived=true"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(url, **_auth(self.pilot)).status_code, 403
        )
        archived = self.client.get(url, **_auth(self.manager)).json()
        self.assertEqual([t["id"] for t in archived], [self.tribe.pk])
        groups_url = f"{BASE_URL}/{self.tribe.pk}/groups?archived=true"
        self.assertEqual(
            self.client.get(groups_url, **_auth(self.pilot)).status_code, 403
        )
        groups = self.client.get(groups_url, **_auth(self.manager)).json()
        self.assertEqual([g["name"] for g in groups], ["Old"])

    def test_a_group_is_restored_only_in_an_active_tribe(self):
        group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Movers",
            code="supply-structure.movers",
            is_active=False,
        )
        self.tribe.is_active = False
        self.tribe.save()
        url = f"/{self.tribe.pk}/groups/{group.pk}"
        refused = self._send("patch", url, self.manager, {"is_active": True})
        self.assertEqual(refused.status_code, 400)
        self.tribe.is_active = True
        self.tribe.save()
        ok = self._send("patch", url, self.manager, {"is_active": True})
        self.assertEqual(ok.status_code, 200)
        group.refresh_from_db()
        self.assertTrue(group.is_active)

    def test_unknown_tribe_or_group_is_404(self):
        self.assertEqual(
            self._send("patch", "/999999", self.manager, {}).status_code, 404
        )
        self.assertEqual(
            self._send(
                "patch",
                f"/{self.tribe.pk}/groups/999999",
                self.manager,
                {},
            ).status_code,
            404,
        )

    # Chiefs

    def test_people_team_swaps_a_chief(self):
        with patch("tribes.tasks.discord"):
            response = self.client.put(
                f"{BASE_URL}/{self.tribe.pk}/chief",
                data=json.dumps({"user_id": self.pilot.pk}),
                content_type="application/json",
                **_auth(self.manager),
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.tribe.refresh_from_db()
        self.assertEqual(self.tribe.chief, self.pilot)
        flag = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}", **_auth(self.manager)
        ).json()["can_set_chief"]
        self.assertTrue(flag)
