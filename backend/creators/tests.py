"""Tests for creator account OAuth, feed, Reddit submit, and ingest."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.utils import timezone

from app.test import TestCase
from creators.clients.reddit import normalize_reddit_username
from creators.models import (
    CreatorAccount,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from creators.oauth import OAuthError, TokenPayload
from creators.service import (
    ensure_valid_access_token,
    poll_twitch_live,
    sync_reddit_posts,
    sync_twitch_videos,
    sync_youtube_videos,
    upsert_account_from_oauth,
)
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


class CreatorAccountsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()

        tribe = Tribe.objects.create(
            name="Pulse", slug="pulse", chief=self.user
        )
        self.thinkspeak = TribeGroup.objects.create(
            tribe=tribe,
            name="Thinkspeak",
            code="pulse.thinkspeak",
        )

        SyncPilotFeaturesCommand().handle()
        feature = PilotFeature.objects.get(code="creators.connect")
        feature.tribe_groups.set([self.thinkspeak])
        clear_feature_cache()

    def _grant_thinkspeak(self, user=None):
        user = user or self.user
        TribeGroupMembership.objects.create(
            user=user,
            tribe_group=self.thinkspeak,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

    def test_connect_denied_without_thinkspeak(self):
        response = self.client.get(
            "/api/creators/twitch/connect",
            {"redirect_url": "https://example.com/done"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["feature"], "creators.connect")

    def test_list_accounts_requires_thinkspeak(self):
        response = self.client.get(
            "/api/creators",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_list_accounts_for_thinkspeak_member(self):
        self._grant_thinkspeak()
        CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="123",
            platform_username="fleetfc",
            access_token="tok",
        )
        response = self.client.get(
            "/api/creators",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["provider"], "twitch")
        self.assertEqual(data[0]["platform_username"], "fleetfc")
        self.assertNotIn("access_token", data[0])

    def test_public_live_and_feed_unauthenticated(self):
        account = CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="99",
            platform_username="livepilot",
            is_live=True,
            live_title="Roaming",
            live_started_at=timezone.now(),
        )
        CreatorItem.objects.create(
            account=account,
            provider=CreatorProvider.TWITCH,
            external_id="v1",
            kind=CreatorItemKind.VOD,
            title="Yesterday's roam",
            url="https://www.twitch.tv/videos/v1",
            published_at=timezone.now(),
        )

        live = self.client.get("/api/creators/live")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(len(live.json()), 1)
        self.assertEqual(live.json()[0]["platform_username"], "livepilot")
        self.assertIn("twitch.tv/livepilot", live.json()[0]["url"])

        feed = self.client.get("/api/creators/feed")
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(len(feed.json()), 1)
        self.assertEqual(feed.json()[0]["title"], "Yesterday's roam")

    @patch("creators.service._fetch_identity")
    @patch("creators.service.exchange_code")
    def test_oauth_upsert_account(self, exchange_code, fetch_identity):
        exchange_code.return_value = TokenPayload(
            access_token="access",
            refresh_token="refresh",
            expires_at=timezone.now() + timedelta(hours=1),
            scopes=["user:read:email"],
            raw={},
        )
        fetch_identity.return_value = {
            "platform_user_id": "twitch-1",
            "platform_username": "fc_main",
            "extra": {"display_name": "FC Main"},
        }
        account = upsert_account_from_oauth(
            self.user, CreatorProvider.TWITCH, "auth-code"
        )
        self.assertEqual(account.platform_user_id, "twitch-1")
        self.assertEqual(account.platform_username, "fc_main")
        self.assertEqual(account.access_token, "access")
        self.assertFalse(account.token_invalid)

        # Reconnect replaces tokens for same user/provider.
        exchange_code.return_value = TokenPayload(
            access_token="access2",
            refresh_token="refresh2",
            expires_at=timezone.now() + timedelta(hours=1),
            scopes=["user:read:email"],
            raw={},
        )
        account2 = upsert_account_from_oauth(
            self.user, CreatorProvider.TWITCH, "auth-code-2"
        )
        self.assertEqual(account2.id, account.id)
        self.assertEqual(account2.access_token, "access2")
        self.assertEqual(CreatorAccount.objects.count(), 1)

    @patch("creators.service.refresh_access_token")
    def test_invalid_refresh_marks_token_invalid(self, refresh):
        account = CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.YOUTUBE,
            platform_user_id="yt-1",
            platform_username="Channel",
            access_token="old",
            refresh_token="bad",
            token_expires_at=timezone.now() - timedelta(minutes=5),
        )
        refresh.side_effect = OAuthError("refresh_failed", "nope")
        token = ensure_valid_access_token(account)
        self.assertIsNone(token)
        account.refresh_from_db()
        self.assertTrue(account.token_invalid)

    def test_normalize_reddit_username_variants(self):
        self.assertEqual(
            normalize_reddit_username("u/BearThatCares"), "BearThatCares"
        )
        self.assertEqual(
            normalize_reddit_username(
                "https://www.reddit.com/user/BearThatCares/"
            ),
            "BearThatCares",
        )
        self.assertEqual(
            normalize_reddit_username(
                "https://www.reddit.com/u/BearThatCares/?utm=1"
            ),
            "BearThatCares",
        )

    @patch("creators.service.list_user_submitted")
    def test_link_reddit_username_and_sync(self, list_submitted):
        self._grant_thinkspeak()
        response = self.client.put(
            "/api/creators/reddit",
            data={"username": "u/ThinkspeakPilot"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "reddit")
        self.assertEqual(
            response.json()["platform_username"], "ThinkspeakPilot"
        )
        self.assertEqual(
            response.json()["platform_user_id"], "thinkspeakpilot"
        )

        account = CreatorAccount.objects.get(
            user=self.user, provider=CreatorProvider.REDDIT
        )
        list_submitted.return_value = [
            {
                "id": "abc123",
                "title": "Recruitment post",
                "url": "https://www.reddit.com/r/eve/comments/abc123/",
                "created_utc": 1723824000,
                "thumbnail": "",
            }
        ]
        count = sync_reddit_posts(account)
        self.assertEqual(count, 1)
        item = CreatorItem.objects.get(
            provider=CreatorProvider.REDDIT, external_id="abc123"
        )
        self.assertEqual(item.kind, CreatorItemKind.REDDIT_POST)
        self.assertEqual(item.title, "Recruitment post")

        feed = self.client.get("/api/creators/feed?provider=reddit")
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(len(feed.json()), 1)

    def test_reddit_oauth_connect_rejected(self):
        self._grant_thinkspeak()
        response = self.client.get(
            "/api/creators/reddit/connect",
            {"redirect_url": "https://example.com/done"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "use_put_reddit_username")

    def test_link_reddit_requires_username(self):
        self._grant_thinkspeak()
        response = self.client.put(
            "/api/creators/reddit",
            data={"username": "  "},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    @patch("creators.service.twitch_app_access_token", return_value="app-tok")
    @patch("creators.service.TwitchClient")
    def test_poll_twitch_live(self, client_cls, app_token):
        del app_token
        live_account = CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="111",
            platform_username="onair",
        )
        offline_user = User.objects.create(username="offline")
        offline = CreatorAccount.objects.create(
            user=offline_user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="222",
            platform_username="offline",
            is_live=True,
            live_title="was live",
        )
        client_cls.return_value.get_streams.return_value = [
            {
                "user_id": "111",
                "title": "Fleet night",
                "started_at": "2026-08-16T16:00:00Z",
            }
        ]
        updated = poll_twitch_live()
        self.assertGreaterEqual(updated, 1)
        live_account.refresh_from_db()
        offline.refresh_from_db()
        self.assertTrue(live_account.is_live)
        self.assertEqual(live_account.live_title, "Fleet night")
        self.assertFalse(offline.is_live)

    @patch("creators.service.twitch_app_access_token", return_value="app-tok")
    @patch("creators.service.TwitchClient")
    def test_sync_twitch_videos_upserts_items(self, client_cls, app_token):
        del app_token
        account = CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="111",
            platform_username="vodder",
        )
        client_cls.return_value.get_videos.return_value = [
            {
                "id": "vod-9",
                "title": "Highlight",
                "url": "https://www.twitch.tv/videos/vod-9",
                "thumbnail_url": "https://static/twitch/%{width}x%{height}.jpg",
                "published_at": "2026-08-15T12:00:00Z",
            }
        ]
        count = sync_twitch_videos(account)
        self.assertEqual(count, 1)
        item = CreatorItem.objects.get(
            provider=CreatorProvider.TWITCH, external_id="vod-9"
        )
        self.assertEqual(item.kind, CreatorItemKind.VOD)
        self.assertEqual(item.title, "Highlight")
        self.assertIn("640x360", item.thumbnail_url)

    @patch("creators.service.ensure_valid_access_token", return_value="yt-tok")
    @patch("creators.service.YouTubeClient")
    def test_sync_youtube_videos_upserts_items(self, client_cls, ensure_token):
        del ensure_token
        account = CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.YOUTUBE,
            platform_user_id="UC123",
            platform_username="FL33T Vids",
            extra={"uploads_playlist_id": "UU123"},
            access_token="yt-tok",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        client_cls.return_value.list_playlist_items.return_value = [
            {
                "contentDetails": {
                    "videoId": "ytVid1",
                    "videoPublishedAt": "2026-08-14T10:00:00Z",
                },
                "snippet": {
                    "title": "Drill Wars",
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/ytVid1/hq.jpg"}
                    },
                },
            }
        ]
        count = sync_youtube_videos(account)
        self.assertEqual(count, 1)
        item = CreatorItem.objects.get(
            provider=CreatorProvider.YOUTUBE, external_id="ytVid1"
        )
        self.assertEqual(item.kind, CreatorItemKind.VIDEO)
        self.assertEqual(item.url, "https://www.youtube.com/watch?v=ytVid1")

    def test_connect_redirects_for_thinkspeak_member(self):
        self._grant_thinkspeak()
        response = self.client.get(
            "/api/creators/twitch/connect",
            {"redirect_url": "https://example.com/done"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("id.twitch.tv/oauth2/authorize", response["Location"])

    def test_connect_accepts_token_query_param(self):
        self._grant_thinkspeak()
        response = self.client.get(
            "/api/creators/twitch/connect",
            {
                "redirect_url": "https://example.com/done",
                "token": self.token,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("id.twitch.tv/oauth2/authorize", response["Location"])

    @patch("creators.router.upsert_account_from_oauth")
    def test_oauth_callback_upserts(self, upsert):
        self._grant_thinkspeak()
        upsert.return_value = MagicMock()
        session = self.client.session
        session["creators_oauth_redirect_url"] = "https://example.com/done"
        session["creators_oauth_state"] = "state-abc"
        session["creators_oauth_provider"] = "twitch"
        session["creators_oauth_user_id"] = self.user.id
        session.save()

        response = self.client.get(
            "/api/creators/twitch/callback",
            {"code": "the-code", "state": "state-abc"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("connected=twitch", response["Location"])
        upsert.assert_called_once_with(
            self.user, CreatorProvider.TWITCH, "the-code"
        )

    def test_disconnect(self):
        self._grant_thinkspeak()
        CreatorAccount.objects.create(
            user=self.user,
            provider=CreatorProvider.TWITCH,
            platform_user_id="123",
            platform_username="fleetfc",
            access_token="tok",
            refresh_token="ref",
        )
        with patch("creators.service.revoke_token") as revoke:
            response = self.client.delete(
                "/api/creators/twitch",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            revoke.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CreatorAccount.objects.filter(
                user=self.user, provider=CreatorProvider.TWITCH
            ).exists()
        )
