"""The site's gate manifest must map onto the registry without losing anyone."""

from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import signals

from app.test import TestCase
from fleets.models import EveFleet
from groups.features.gate_manifest import (
    LOSS_ALLOWED_PARITY,
    load_gates,
)
from groups.features.registry import FEATURE_DEFINITIONS
from groups.features.types import FeatureScope
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.audit_frontend_gate_parity import audit
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import AffiliationType, PilotFeature, UserAffiliation
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

PARITY_CLASSES = {"", "superuser_gain", "dead_ui", "custom"}


def _granting_permissions(definition) -> set[str]:
    """Permissions that open a feature on their own, whatever its wiring."""
    granted = {definition.legacy_permission} - {""}
    if definition.scope in (FeatureScope.STAFF, FeatureScope.TRIBE_CHIEF):
        granted |= {definition.staff_permission} - {""}
    return granted


class GateManifestTestCase(TestCase):
    def setUp(self):
        self.gates = load_gates()

    def test_every_gate_names_a_registry_feature(self):
        unknown = [
            gate.key
            for gate in self.gates
            if gate.feature not in FEATURE_DEFINITIONS
        ]
        self.assertEqual(unknown, [])

    def test_parity_classes_are_known(self):
        for gate in self.gates:
            with self.subTest(gate=gate.key):
                self.assertIn(gate.parity, PARITY_CLASSES)
                self.assertEqual(gate.custom, gate.parity == "custom")

    def test_legacy_permissions_exist(self):
        for gate in self.gates:
            for dotted in gate.perms:
                app_label, codename = dotted.split(".")
                with self.subTest(gate=gate.key, perm=dotted):
                    self.assertTrue(
                        Permission.objects.filter(
                            content_type__app_label=app_label,
                            codename=codename,
                        ).exists()
                    )

    def test_holders_of_the_old_permission_keep_the_gate(self):
        """Losses are impossible by construction outside dead_ui gates."""
        for gate in self.gates:
            if gate.custom or gate.parity in LOSS_ALLOWED_PARITY:
                continue
            granted = _granting_permissions(FEATURE_DEFINITIONS[gate.feature])
            with self.subTest(gate=gate.key):
                self.assertTrue(set(gate.perms) <= granted)

    def test_superuser_only_gates_stay_superuser_only(self):
        for gate in self.gates:
            if gate.perms or gate.custom:
                continue
            definition = FEATURE_DEFINITIONS[gate.feature]
            with self.subTest(gate=gate.key):
                self.assertTrue(gate.superuser)
                self.assertEqual(definition.scope, FeatureScope.AUTH_GROUP)
                self.assertFalse(definition.legacy_permission)
                self.assertFalse(definition.default_auth_group_names)

    def test_strict_gates_only_differ_for_superusers(self):
        for gate in self.gates:
            if gate.key.endswith("#strict"):
                with self.subTest(gate=gate.key):
                    self.assertFalse(gate.superuser)
                    self.assertEqual(gate.parity, "superuser_gain")


class GateParityAuditTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )
        signals.post_save.disconnect(
            sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
        )
        self.alliance = AffiliationType.objects.create(
            name="Alliance",
            group=Group.objects.create(name="Alliance Group"),
            priority=10,
            default=False,
        )
        pulse = Tribe.objects.create(name="Pulse", slug="pulse")
        self.thinkspeak = TribeGroup.objects.create(
            tribe=pulse, name="Thinkspeak", code="pulse.thinkspeak"
        )
        clear_feature_cache()
        SyncCommand().handle()
        clear_feature_cache()
        self.gates = load_gates()

    def tearDown(self):
        clear_feature_cache()

    def _rows(self, users):
        return audit(self.gates, users)

    def test_reports_gains_from_wider_wiring(self):
        member = User.objects.create_user(username="wired_member")
        UserAffiliation.objects.create(user=member, affiliation=self.alliance)
        # fleets.view is resource_match, so the profile bridge doesn't add
        # its permission: the frontend hides fleets today, features show it.
        report = self._rows([member])
        self.assertEqual(report["fleets.view"]["gains"], [member.id])
        self.assertEqual(report["fleets.view"]["losses"], [])
        # campaigns.view is affiliation scope: the bridge already lists it.
        self.assertEqual(report["campaigns.view"]["gains"], [])

    def test_permission_holders_lose_nothing(self):
        holder = User.objects.create_user(username="holder")
        for gate in self.gates:
            for dotted in gate.perms:
                app_label, codename = dotted.split(".")
                holder.user_permissions.add(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )
        report = self._rows([User.objects.get(pk=holder.pk)])
        losses = {
            key: row["losses"]
            for key, row in report.items()
            if row["losses"] and row["parity"] not in LOSS_ALLOWED_PARITY
        }
        self.assertEqual(losses, {})

    def test_superusers_see_no_change(self):
        # Django lists every permission for an active superuser, so even the
        # strict gates (no superuser OR) already let them in.
        root = User.objects.create_user(username="root", is_superuser=True)
        report = self._rows([root])
        self.assertFalse(any(row["gains"] for row in report.values()))
        self.assertFalse(any(row["losses"] for row in report.values()))

    def test_thinkspeak_members_keep_content_manage(self):
        member = User.objects.create_user(username="ts")
        TribeGroupMembership.objects.create(
            user=member,
            tribe_group=self.thinkspeak,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        report = self._rows([member])
        self.assertEqual(report["content.manage"]["losses"], [])
        self.assertEqual(report["content.manage"]["gains"], [])

    def test_command_fails_on_unexpected_loss(self):
        holder = User.objects.create_user(username="holder")
        holder.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="posts", codename="add_evepost"
            )
        )
        out = StringIO()
        call_command("audit_frontend_gate_parity", stdout=out)
        self.assertIn("No unexpected losses.", out.getvalue())

        # An admin narrows posts.create so the old permission no longer
        # opens it: the audit must refuse.
        PilotFeature.objects.filter(code="posts.create").update(
            legacy_permission=""
        )
        clear_feature_cache()
        with self.assertRaises(CommandError):
            call_command("audit_frontend_gate_parity", stdout=StringIO())
