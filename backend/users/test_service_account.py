"""The Discord bot's service account (shadow mode: staff still pass)."""

import io

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.core.cache import cache
from django.core.management import call_command

from app.test import TestCase as SiteTestCase
from authentication import has_service_account_permission, is_service_account
from users.jwt_auth import encode_jwt


def grant_service_account(user):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="users", codename="service_account"
        )
    )


class ServiceAccountTest(SiteTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.bot = User.objects.create(username="bot")
        grant_service_account(self.bot)
        self.bot_token = encode_jwt({"user_id": self.bot.id})

    def test_member_and_anonymous_are_not_the_bot(self):
        self.assertFalse(is_service_account(self.user))
        self.assertFalse(is_service_account(AnonymousUser()))
        self.assertFalse(is_service_account(None))

    def test_permission_holder_is_the_bot_without_staff(self):
        self.assertFalse(self.bot.is_staff or self.bot.is_superuser)
        self.assertTrue(has_service_account_permission(self.bot))
        with self.assertNoLogs("authentication", level="WARNING"):
            self.assertTrue(is_service_account(self.bot))

    def test_superuser_alone_does_not_hold_the_permission(self):
        self.make_superuser()
        self.assertFalse(has_service_account_permission(self.user))

    def test_staff_fallback_still_passes_and_is_logged_once(self):
        for flag in ("is_staff", "is_superuser"):
            with self.subTest(flag=flag):
                cache.clear()
                user = User.objects.create(username=f"u-{flag}")
                setattr(user, flag, True)
                user.save()
                with self.assertLogs("authentication", "WARNING") as logs:
                    self.assertTrue(is_service_account(user))
                    self.assertTrue(is_service_account(user))
                self.assertEqual(len(logs.output), 1)
                self.assertIn(f"user_id={user.pk}", logs.output[0])

    def test_bot_only_endpoint_accepts_the_bot_and_rejects_members(self):
        def sync(token):
            return self.client.post(
                "/api/discord/guilds/sync",
                {"guilds": []},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(sync(self.bot_token).status_code, 200)
        self.assertEqual(sync(self.token).status_code, 403)

    def test_npsi_bot_may_act_for_another_user(self):
        # pylint: disable=import-outside-toplevel
        # (importing npsi_actions first hits an existing import cycle)
        from fleets.endpoints import (  # noqa: F401  pylint: disable=unused-import
            router,
        )
        from fleets.helpers.npsi_actions import (
            NpsiActionError,
            authorize_npsi_actor,
        )

        actor = User.objects.create(username="fc")
        authorize_npsi_actor(requester=self.bot, actor=actor, fc_user=actor)
        with self.assertRaises(NpsiActionError):
            authorize_npsi_actor(
                requester=self.user, actor=actor, fc_user=actor
            )

    def test_management_command(self):
        out = io.StringIO()
        call_command("service_account", "--grant", self.user.id, stdout=out)
        self.assertTrue(has_service_account_permission(self.user))
        call_command("service_account", "--list", stdout=out)
        self.assertIn(f"{self.user.id}\t{self.user.username}", out.getvalue())
        call_command("service_account", "--revoke", self.user.id, stdout=out)
        self.assertFalse(has_service_account_permission(self.user))
