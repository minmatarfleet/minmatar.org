"""Tests for per-group affiliation allowlists on tribe apply/offboarding."""

import jwt
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import Client, TestCase

from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import AffiliationType, PilotFeature, UserAffiliation
from tribes.helpers.offboarding import (
    offboard_tribe_memberships_without_feature,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
)

BASE_URL = "/api/tribes"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


class TribeGroupAffiliationGateTestCase(TestCase):
    def setUp(self):
        django_signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        clear_feature_cache()
        SyncCommand().handle()
        self.client = Client()

        self.alliance = AffiliationType.objects.create(
            name="Alliance",
            group=Group.objects.create(name="Alliance Aff Gate"),
            priority=100,
            default=False,
        )
        self.associate = AffiliationType.objects.create(
            name="Associate",
            group=Group.objects.create(name="Associate Aff Gate"),
            priority=90,
            default=False,
        )
        self.militia = AffiliationType.objects.create(
            name="Militia",
            group=Group.objects.create(name="Militia Aff Gate"),
            priority=80,
            default=False,
        )

        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.set([self.alliance, self.associate])
        feature.tribe_groups.clear()
        feature.legacy_permission = ""
        feature.save(update_fields=["legacy_permission"])
        clear_feature_cache()

        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals-aff")
        self.alliance_only = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", code="capitals.dreads-aff"
        )
        self.alliance_only.allowed_affiliations.set([self.alliance])
        self.open_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Carriers", code="capitals.carriers-aff"
        )
        self.open_group.allowed_affiliations.set(
            [self.alliance, self.associate]
        )

        self.user = User.objects.create_user(username="aff_gate_user")
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.alliance
        )
        self.token = _make_token(self.user)

    def tearDown(self):
        clear_feature_cache()

    def test_apply_denied_when_affiliation_not_allowed(self):
        UserAffiliation.objects.filter(user=self.user).delete()
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.associate
        )
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.alliance_only.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["feature"], "tribes.apply")

    def test_apply_allowed_for_matching_affiliation(self):
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.alliance_only.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_group_schema_includes_can_apply_and_affiliations(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.alliance_only.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["can_apply"])
        names = {a["name"] for a in data["allowed_affiliations"]}
        self.assertEqual(names, {"Alliance"})

        UserAffiliation.objects.filter(user=self.user).delete()
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.militia
        )
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.alliance_only.pk}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertFalse(response.json()["can_apply"])

    def test_offboard_only_ineligible_memberships(self):
        alliance_membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.alliance_only,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        open_membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.open_group,
            status=TribeGroupMembership.STATUS_PENDING,
        )

        django_signals.post_save.disconnect(
            sender=UserAffiliation,
            dispatch_uid="user_affiliation_post_save",
        )
        django_signals.post_delete.disconnect(
            sender=UserAffiliation,
            dispatch_uid="user_affiliation_post_delete",
        )
        try:
            UserAffiliation.objects.filter(user=self.user).delete()
            UserAffiliation.objects.create(
                user=self.user, affiliation=self.associate
            )
            count = offboard_tribe_memberships_without_feature(self.user)
        finally:
            # pylint: disable-next=import-outside-toplevel
            from groups.signals import (  # noqa: PLC0415
                user_affiliation_post_delete,
                user_affiliation_post_save,
            )

            django_signals.post_save.connect(
                user_affiliation_post_save,
                sender=UserAffiliation,
                dispatch_uid="user_affiliation_post_save",
            )
            django_signals.post_delete.connect(
                user_affiliation_post_delete,
                sender=UserAffiliation,
                dispatch_uid="user_affiliation_post_delete",
            )

        self.assertEqual(count, 1)
        alliance_membership.refresh_from_db()
        open_membership.refresh_from_db()
        self.assertEqual(
            alliance_membership.status, TribeGroupMembership.STATUS_INACTIVE
        )
        history = TribeGroupMembershipHistory.objects.filter(
            membership=alliance_membership,
            to_status=TribeGroupMembership.STATUS_INACTIVE,
        ).latest("changed_at")
        self.assertEqual(history.reason, "removed")
        self.assertEqual(
            open_membership.status, TribeGroupMembership.STATUS_PENDING
        )
