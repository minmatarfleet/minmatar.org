from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from creators.announce import announce_new_items
from creators.models import (
    CreatorAccount,
    CreatorAccountStatus,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from creators.service import sync_youtube_videos


@patch("creators.announce.queue_channel_message")
class AnnounceNewItemsTestCase(TestCase):
    def setUp(self):
        user = User.objects.create(username="fleet")
        self.account = CreatorAccount.objects.create(
            user=user,
            provider=CreatorProvider.YOUTUBE,
            platform_user_id="UCfleet",
            platform_username="Minmatar Fleet",
            discord_channel_id="555",
        )

    def item(self, external_id, *, age=timedelta(hours=1), **fields):
        return CreatorItem.objects.create(
            account=self.account,
            provider=CreatorProvider.YOUTUBE,
            external_id=external_id,
            kind=CreatorItemKind.VIDEO,
            title=fields.pop("title", f"Video {external_id}"),
            url=f"https://www.youtube.com/watch?v={external_id}",
            published_at=timezone.now() - age,
            **fields,
        )

    def test_posts_new_items_oldest_first(self, queue):
        new = self.item("b", title="Newest")
        earlier = self.item("a", title="Earlier", age=timedelta(hours=5))

        self.assertEqual(
            announce_new_items(self.account), [earlier.id, new.id]
        )
        self.assertEqual(
            [c.kwargs["message"] for c in queue.call_args_list],
            [
                "New video from Minmatar Fleet: **Earlier**\n"
                "https://www.youtube.com/watch?v=a",
                "New video from Minmatar Fleet: **Newest**\n"
                "https://www.youtube.com/watch?v=b",
            ],
        )
        self.assertEqual(queue.call_args.args, ("555",))
        new.refresh_from_db()
        self.assertIsNotNone(new.announced_at)

    def test_each_item_posts_once(self, queue):
        self.item("a")
        announce_new_items(self.account)
        announce_new_items(self.account)
        self.assertEqual(queue.call_count, 1)

    def test_skips_old_and_hidden_items(self, queue):
        self.item("old", age=timedelta(days=5))
        self.item("hidden", hidden=True)
        self.assertEqual(announce_new_items(self.account), [])
        queue.assert_not_called()

    def test_no_channel_posts_nothing(self, queue):
        self.account.discord_channel_id = ""
        self.item("a")
        self.assertEqual(announce_new_items(self.account), [])
        queue.assert_not_called()

    def test_suspended_account_posts_nothing(self, queue):
        self.account.status = CreatorAccountStatus.SUSPENDED
        self.item("a")
        self.assertEqual(announce_new_items(self.account), [])
        queue.assert_not_called()

    def test_skips_items_before_import_start(self, queue):
        self.account.import_start_at = timezone.now() - timedelta(hours=2)
        self.item("before", age=timedelta(hours=3))
        after = self.item("after", age=timedelta(hours=1))
        self.assertEqual(announce_new_items(self.account), [after.id])
        queue.assert_called_once()

    @patch("creators.service.ensure_valid_access_token", return_value="tok")
    @patch("creators.service.YouTubeClient")
    def test_youtube_sync_skips_media_before_import_start(
        self, client, token, queue
    ):
        self.account.extra = {"uploads_playlist_id": "UUfleet"}
        self.account.import_start_at = timezone.now() - timedelta(days=1)
        self.account.save()
        old = (timezone.now() - timedelta(days=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        new = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        client.return_value.list_playlist_items.return_value = [
            {
                "contentDetails": {"videoId": vid, "videoPublishedAt": ts},
                "snippet": {"title": vid},
                "status": {"privacyStatus": "public"},
            }
            for vid, ts in (("old", old), ("new", new))
        ]

        self.assertEqual(sync_youtube_videos(self.account), 1)

        token.assert_called()
        self.assertEqual(
            list(CreatorItem.objects.values_list("external_id", flat=True)),
            ["new"],
        )
        queue.assert_called_once()

    @patch("creators.service.ensure_valid_access_token", return_value="tok")
    @patch("creators.service.YouTubeClient")
    def test_youtube_sync_posts_new_upload(self, client, token, queue):
        self.account.extra = {"uploads_playlist_id": "UUfleet"}
        self.account.save()
        published = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        client.return_value.list_playlist_items.return_value = [
            {
                "contentDetails": {
                    "videoId": "short1",
                    "videoPublishedAt": published,
                },
                "snippet": {"title": "Fourth campaign, who dis?"},
                "status": {"privacyStatus": "public"},
            }
        ]

        sync_youtube_videos(self.account)
        sync_youtube_videos(self.account)

        token.assert_called()
        queue.assert_called_once()
        self.assertIn(
            "**Fourth campaign, who dis?**", queue.call_args.kwargs["message"]
        )
