"""Creator moderation: access, feed effects and audit entries."""

from django.contrib.auth.models import User

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from creators.models import (
    CreatorAccount,
    CreatorAccountStatus,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from eveonline.models import EveCharacter, EvePlayer
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

BASE = "/api/creators/moderation"


class CreatorModerationTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        tribe = Tribe.objects.create(
            name="Pulse", slug="pulse", chief=self.user
        )
        group = TribeGroup.objects.create(
            tribe=tribe, name="Thinkspeak", code="pulse.thinkspeak"
        )
        SyncPilotFeaturesCommand().handle()
        PilotFeature.objects.get(code="creators.moderate").tribe_groups.set(
            [group]
        )
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        clear_feature_cache()
        self.outsider = User.objects.create(username="outsider")
        creator = User.objects.create(username="creator")
        self.account = CreatorAccount.objects.create(
            user=creator,
            provider=CreatorProvider.YOUTUBE,
            platform_user_id="yt1",
            platform_username="Creator",
        )
        self.item = CreatorItem.objects.create(
            account=self.account,
            provider=CreatorProvider.YOUTUBE,
            external_id="v1",
            kind=CreatorItemKind.VIDEO,
            title="A video",
        )

    def _put(self, path, body, user=None):
        return self.client.put(
            f"{BASE}/{path}",
            body,
            content_type="application/json",
            **auth_headers(user or self.user),
        )

    def _feed_ids(self):
        return [
            i["external_id"]
            for i in self.client.get("/api/creators/feed").json()
        ]

    def test_outsiders_are_refused(self):
        headers = auth_headers(self.outsider)
        self.assertEqual(
            self.client.get(f"{BASE}/accounts", **headers).status_code, 403
        )
        response = self._put(
            f"accounts/{self.account.pk}/status",
            {"status": "suspended"},
            user=self.outsider,
        )
        self.assertEqual(response.status_code, 403)
        response = self._put(
            f"items/{self.item.pk}", {"hidden": True}, user=self.outsider
        )
        self.assertEqual(response.status_code, 403)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, CreatorAccountStatus.APPROVED)

    def test_list_accounts_counts_items(self):
        response = self.client.get(
            f"{BASE}/accounts", **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]
        self.assertEqual(row["item_count"], 1)
        self.assertEqual(row["status"], "approved")

    def test_suspending_removes_the_account_from_the_feed(self):
        self.assertEqual(self._feed_ids(), ["v1"])
        response = self._put(
            f"accounts/{self.account.pk}/status", {"status": "suspended"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._feed_ids(), [])
        self._put(f"accounts/{self.account.pk}/status", {"status": "approved"})
        self.assertEqual(self._feed_ids(), ["v1"])
        self.assertEqual(AuditEntry.objects.filter(user=self.user).count(), 2)

    def test_bad_status_is_rejected(self):
        response = self._put(
            f"accounts/{self.account.pk}/status", {"status": "banned"}
        )
        self.assertEqual(response.status_code, 400)

    def test_hide_and_feature_items(self):
        other = CreatorItem.objects.create(
            account=self.account,
            provider=CreatorProvider.YOUTUBE,
            external_id="v2",
            kind=CreatorItemKind.VIDEO,
            title="Newer",
        )
        self.assertEqual(self._feed_ids(), ["v2", "v1"])
        self._put(f"items/{self.item.pk}", {"featured": True})
        self.assertEqual(self._feed_ids(), ["v1", "v2"])
        self._put(f"items/{other.pk}", {"hidden": True})
        self.assertEqual(self._feed_ids(), ["v1"])
        listing = self.client.get(
            f"{BASE}/accounts/{self.account.pk}/items",
            **auth_headers(self.user),
        )
        self.assertEqual(len(listing.json()), 2)
        self.assertEqual(AuditEntry.objects.filter(user=self.user).count(), 2)

    def test_unchanged_action_writes_no_audit_entry(self):
        self._put(f"items/{self.item.pk}", {"hidden": False})
        self.assertFalse(AuditEntry.objects.exists())

    def test_items_filter_by_view_and_search_and_page(self):
        for index in range(3):
            CreatorItem.objects.create(
                account=self.account,
                provider=CreatorProvider.YOUTUBE,
                external_id=f"h{index}",
                kind=CreatorItemKind.VIDEO,
                title=f"Hidden roam {index}",
                hidden=True,
            )
        self.item.featured = True
        self.item.save()
        url = f"{BASE}/accounts/{self.account.pk}/items"
        headers = auth_headers(self.user)

        def titles(query):
            return [
                i["title"]
                for i in self.client.get(f"{url}?{query}", **headers).json()
            ]

        self.assertEqual(titles("view=featured"), ["A video"])
        self.assertEqual(len(titles("view=hidden")), 3)
        self.assertEqual(titles("view=shown"), ["A video"])
        self.assertEqual(len(titles("q=roam")), 3)
        self.assertEqual(len(titles("view=hidden&limit=2")), 2)
        self.assertEqual(len(titles("view=hidden&offset=2&limit=2")), 1)
        bad = self.client.get(f"{url}?view=nope", **headers)
        self.assertEqual(bad.status_code, 400)

        counts = self.client.get(
            f"{BASE}/accounts/{self.account.pk}/item-counts", **headers
        ).json()
        self.assertEqual(counts, {"shown": 1, "featured": 1, "hidden": 3})
        counts = self.client.get(
            f"{BASE}/accounts/{self.account.pk}/item-counts?q=video",
            **headers,
        ).json()
        self.assertEqual(counts, {"shown": 1, "featured": 1, "hidden": 0})

    def test_item_counts_are_refused_to_outsiders(self):
        response = self.client.get(
            f"{BASE}/accounts/{self.account.pk}/item-counts",
            **auth_headers(self.outsider),
        )
        self.assertEqual(response.status_code, 403)

    def test_accounts_name_the_owners_main(self):
        main = EveCharacter.objects.create(
            character_id=90000001,
            character_name="Creator Main",
            user=self.account.user,
        )
        EvePlayer.objects.update_or_create(
            user=self.account.user, defaults={"primary_character": main}
        )
        row = self.client.get(
            f"{BASE}/accounts", **auth_headers(self.user)
        ).json()[0]
        self.assertEqual(row["character_id"], 90000001)
        self.assertEqual(row["character_name"], "Creator Main")
