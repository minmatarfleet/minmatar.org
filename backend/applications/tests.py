import importlib
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Permission, User
from django.db.models import signals
from django.test import Client, override_settings
from django.utils.dateparse import parse_datetime

from app.test import TestCase
from applications.discord import notify_application_transferred
from applications.tasks import notify_application_transferred_task
from applications.joined import accept_applications_of_members
from applications.l3arn import (
    L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH,
    L3ARN_CORPORATION_NAME,
    application_discord_description,
    validate_l3arn_application_description,
)
from applications.models import EveCorporationApplication
from applications.prime_time import (
    apply_application_prime_time,
    parse_application_prime_time,
)
from applications.signals import eve_corporation_application_post_save
from applications.tasks import (
    accept_applications_of_members_task,
    sync_application_thread_task,
)
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from eveonline.helpers.characters import set_primary_character, user_player

restore_deleted_applications = importlib.import_module(
    "applications.migrations.0005_restore_deleted_corporation_applications"
).restore_deleted_applications

BASE_URL = "/api/applications/"


# Create your tests here.
class EveCorporationApplicationTestCase(TestCase):
    """Test case for the application endpoints."""

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def test_get_eve_corporation_applications_success(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
        )

        response = self.client.get(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "application_id": application.id,
                    "status": application.status,
                    "user_id": application.user.id,
                    "corporation_id": application.corporation_id,
                }
            ],
        )

    def test_create_corporation_application_blocked_while_one_is_open(self):
        first_corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="First Corporation",
        )
        second_corporation = EveCorporation.objects.create(
            corporation_id=456,
            name="Second Corporation",
        )
        EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=first_corporation.corporation_id,
            description="Already waiting",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{second_corporation.corporation_id}/applications",
            data={"description": "I want this one too."},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "You already have an open application to First Corporation. "
            "Wait for a decision before applying again.",
        )
        self.assertEqual(
            EveCorporationApplication.objects.filter(user=self.user).count(),
            1,
        )

    def test_create_corporation_application_allowed_after_decision(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        decided = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Earlier application",
            status="rejected",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            data={"description": "Trying again."},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            EveCorporationApplication.objects.filter(user=self.user).count(),
            2,
        )
        self.assertEqual(decided.status, "rejected")

    def test_create_corporation_application_ignores_another_users_open_application(
        self,
    ):
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        other = User.objects.create(username="someone-else")
        EveCorporationApplication.objects.create(
            user=other,
            corporation_id=corporation.corporation_id,
            description="Not mine",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            data={"description": "My application."},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)

    def test_get_my_open_application(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Waiting",
        )

        response = self.client.get(
            f"{BASE_URL}me/open",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "application_id": application.id,
                "corporation_id": corporation.corporation_id,
                "corporation_name": corporation.name,
                "status": "pending",
            },
        )

    def test_get_my_open_application_when_none_is_open(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Already decided",
            status="accepted",
        )

        response = self.client.get(
            f"{BASE_URL}me/open",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    def test_accept_corporation_application_success(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123, name="Test Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
        )

        permission = Permission.objects.get(
            codename="change_evecorporationapplication"
        )
        self.user.user_permissions.add(permission)
        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications/{application.id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(application.status, "accepted")

    def test_accept_corporation_application_failure_unauthorized(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123, name="Test Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications/{application.id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(application.status, "pending")

    def test_reject_corporation_application_success(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123, name="Test Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
        )

        permission = Permission.objects.get(
            codename="change_evecorporationapplication"
        )
        self.user.user_permissions.add(permission)
        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications/{application.id}/reject",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(application.status, "rejected")

    def test_reject_corporation_application_failure_unauthorized(self):
        corporation = EveCorporation.objects.create(
            corporation_id=123, name="Test Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications/{application.id}/reject",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(application.status, "pending")

    @patch("applications.router.notify_application_transferred_task")
    def test_transfer_corporation_application_success(self, task_mock):
        source_corporation = EveCorporation.objects.create(
            corporation_id=123, name="Source Corporation"
        )
        target_corporation = EveCorporation.objects.create(
            corporation_id=456, name="Target Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=source_corporation.corporation_id,
            description="Test application",
            discord_thread_id=999,
        )

        permission = Permission.objects.get(
            codename="change_evecorporationapplication"
        )
        self.user.user_permissions.add(permission)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{BASE_URL}corporations/{source_corporation.corporation_id}/applications/{application.id}/transfer",
                data={"corporation_id": target_corporation.corporation_id},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(response.status_code, 200)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(
            application.corporation_id, target_corporation.corporation_id
        )
        self.assertEqual(application.status, "pending")
        self.assertEqual(
            response.json(),
            {
                "application_id": application.id,
                "status": "pending",
                "user_id": application.user.id,
                "corporation_id": target_corporation.corporation_id,
            },
        )
        task_mock.delay.assert_called_once_with(
            application.id,
            source_corporation.corporation_id,
            self.user.username,
        )

    @patch("applications.tasks.notify_application_transferred")
    def test_transfer_notice_task_posts_and_survives_errors(self, notify_mock):
        corporation = EveCorporation.objects.create(
            corporation_id=456, name="Target Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation.corporation_id,
            description="Test application",
            discord_thread_id=999,
        )
        notify_application_transferred_task(application.id, 123, "Recruiter")
        notify_mock.assert_called_once_with(
            application,
            previous_corporation_id=123,
            transferred_by_username="Recruiter",
        )

        notify_mock.side_effect = RuntimeError("discord down")
        with self.assertLogs("applications.tasks", level="ERROR"):
            notify_application_transferred_task(
                application.id, 123, "Recruiter"
            )
        notify_application_transferred_task(987654, 123, "Recruiter")

    def test_transfer_corporation_application_failure_unauthorized(self):
        source_corporation = EveCorporation.objects.create(
            corporation_id=123, name="Source Corporation"
        )
        target_corporation = EveCorporation.objects.create(
            corporation_id=456, name="Target Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=source_corporation.corporation_id,
            description="Test application",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{source_corporation.corporation_id}/applications/{application.id}/transfer",
            data={"corporation_id": target_corporation.corporation_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(
            application.corporation_id, source_corporation.corporation_id
        )

    def test_transfer_corporation_application_rejects_non_pending(self):
        source_corporation = EveCorporation.objects.create(
            corporation_id=123, name="Source Corporation"
        )
        target_corporation = EveCorporation.objects.create(
            corporation_id=456, name="Target Corporation"
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=source_corporation.corporation_id,
            description="Test application",
            status="accepted",
        )

        permission = Permission.objects.get(
            codename="change_evecorporationapplication"
        )
        self.user.user_permissions.add(permission)
        response = self.client.post(
            f"{BASE_URL}corporations/{source_corporation.corporation_id}/applications/{application.id}/transfer",
            data={"corporation_id": target_corporation.corporation_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        application = EveCorporationApplication.objects.get(id=application.id)
        self.assertEqual(
            application.corporation_id, source_corporation.corporation_id
        )


class L3arnCorporationApplicationValidationTest(TestCase):
    """L3ARN application description length validation."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        self.client = Client()
        super().setUp()

    def test_validate_l3arn_application_description_rejects_over_limit(self):
        over_limit = "x" * (L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH + 1)
        self.assertIsNotNone(
            validate_l3arn_application_description(over_limit)
        )

        within_limit = "x" * L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH
        self.assertIsNone(validate_l3arn_application_description(within_limit))

    def test_validate_l3arn_application_description_ignores_web_only_how_found_line(
        self,
    ):
        how_found_line = (
            "\n- How I found you: I saw a Reddit post by Minmatar Fleet"
        )
        within_limit = (
            "x"
            * (L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH - len(how_found_line))
            + how_found_line
        )
        self.assertIsNone(validate_l3arn_application_description(within_limit))

        over_limit = (
            "x" * (L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH + 1)
            + how_found_line
        )
        self.assertIsNotNone(
            validate_l3arn_application_description(over_limit)
        )

    def test_application_discord_description_strips_how_found_line(self):
        description = (
            "Questionnaire:\n"
            "- Goals in EVE: FW\n"
            "- How I found you: Other (friend)\n"
            "- Other corps considered: none"
        )
        self.assertEqual(
            application_discord_description(description),
            "Questionnaire:\n"
            "- Goals in EVE: FW\n"
            "- Other corps considered: none",
        )

    def test_create_l3arn_application_rejects_over_limit_description(self):
        corporation = EveCorporation.objects.create(
            corporation_id=98696436,
            name=L3ARN_CORPORATION_NAME,
        )
        over_limit = "x" * (L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH + 1)

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            data={"description": over_limit},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            EveCorporationApplication.objects.filter(
                corporation_id=corporation.corporation_id
            ).count(),
            0,
        )


@override_settings(WEB_LINK_URL="https://my.minmatar.org")
class EveCorporationApplicationSignalTest(TestCase):
    """Test case for the application signal handlers."""

    def setUp(self):
        super().setUp()
        signals.post_save.connect(
            eve_corporation_application_post_save,
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=123, name="Test Corporation"
        )
        char = EveCharacter.objects.create(
            character_id=1234,
            character_name="Mr User",
            user=self.user,
        )
        set_primary_character(self.user, char)
        DiscordUser.objects.create(
            id=1,
            discord_tag="MrUser",
            user=self.user,
        )
        discord_patch = patch("applications.discord.discord")
        self.discord_mock = discord_patch.start()
        self.addCleanup(discord_patch.stop)
        self.discord_mock.create_forum_thread.return_value.json.return_value = {
            "id": "555"
        }

    def _create(self, **fields):
        return EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=self.corporation.corporation_id,
            description="Test application",
            **fields,
        )

    def test_application_post_save_signal(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._create(status="accepted")

        self.discord_mock.create_message.assert_called()
        message = self.discord_mock.create_message.call_args.kwargs["message"]
        self.assertIn("https://my.minmatar.org/learning/", message)
        self.assertIn("Learning Center", message)
        self.assertNotIn("wiki.minmatar.org", message)

    def test_save_queues_thread_instead_of_calling_discord(self):
        with patch(
            "applications.signals.sync_application_thread_task"
        ) as task_mock:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                application = self._create()

            self.assertEqual([], self.discord_mock.mock_calls)
            task_mock.delay.assert_not_called()
            self.assertEqual(1, len(callbacks))

            callbacks[0]()
        task_mock.delay.assert_called_once_with(application.pk, "pending")

    def test_thread_is_created_once_with_the_same_starter_message(self):
        with self.captureOnCommitCallbacks(execute=True):
            application = self._create()

        application.refresh_from_db()
        self.assertEqual(555, application.discord_thread_id)
        self.discord_mock.create_forum_thread.assert_called_once()
        kwargs = self.discord_mock.create_forum_thread.call_args.kwargs
        self.assertEqual("Mr User - Test Corporation", kwargs["title"])
        self.assertEqual(
            "<@1>\n\n"
            "Main Character: Mr User\n"
            "Applying to: Test Corporation\n"
            "Description: Test application\n"
            "https://my.minmatar.org/alliance/corporations/application/"
            f"123/{application.pk}\n",
            kwargs["message"],
        )
        self.discord_mock.create_message.assert_not_called()
        self.discord_mock.close_thread.assert_not_called()

    def test_pending_save_with_thread_queues_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            application = self._create(discord_thread_id=777)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            application.description = "edited"
            application.save()

        self.assertEqual([], callbacks)
        self.assertEqual([], self.discord_mock.mock_calls)

    def test_reject_posts_notice_after_commit(self):
        application = self._create(discord_thread_id=777)
        application.status = "rejected"
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            application.save()
        self.assertEqual([], self.discord_mock.mock_calls)

        for callback in callbacks:
            callback()
        self.discord_mock.create_message.assert_called_once_with(
            channel_id=777,
            message=":bangbang: Your application has been rejected, "
            "please contact your recruiter for more information",
        )
        self.discord_mock.close_thread.assert_called_once_with(channel_id=777)
        self.discord_mock.create_forum_thread.assert_not_called()

    def test_discord_failure_does_not_fail_the_save(self):
        self.discord_mock.create_forum_thread.side_effect = RuntimeError(
            "discord down"
        )
        with patch(
            "applications.signals.sync_application_thread_task"
        ) as task_mock:
            with self.captureOnCommitCallbacks(execute=True):
                application = self._create()
        (application_id, status), _ = task_mock.delay.call_args

        with self.assertLogs("applications.tasks", level="ERROR"):
            result = sync_application_thread_task.apply(
                args=(application_id, status), retries=3
            )

        self.assertTrue(result.successful())
        self.discord_mock.create_forum_thread.assert_called_once()
        application.refresh_from_db()
        self.assertIsNone(application.discord_thread_id)
        self.assertEqual("pending", application.status)

    def test_broker_outage_does_not_fail_the_save(self):
        with patch(
            "applications.signals.sync_application_thread_task"
        ) as task_mock:
            task_mock.delay.side_effect = ConnectionError("broker down")
            with self.assertLogs("applications.signals", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    application = self._create()

        self.assertTrue(
            EveCorporationApplication.objects.filter(
                pk=application.pk
            ).exists()
        )
        self.assertEqual([], self.discord_mock.mock_calls)

    def test_delete_queues_thread_close(self):
        application = self._create(discord_thread_id=777)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            application.delete()
        self.assertEqual([], self.discord_mock.mock_calls)

        for callback in callbacks:
            callback()
        self.discord_mock.create_message.assert_called_once_with(
            channel_id=777,
            message=":bangbang: This application has been deleted",
        )
        self.discord_mock.close_thread.assert_called_once_with(channel_id=777)


class NotifyApplicationTransferredTest(TestCase):
    def test_notify_application_transferred_updates_thread(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )

        source_corporation = EveCorporation.objects.create(
            corporation_id=123, name="Source Corporation"
        )
        target_corporation = EveCorporation.objects.create(
            corporation_id=456, name="Target Corporation"
        )
        char = EveCharacter.objects.create(
            character_id=1234,
            character_name="Mr User",
            user=self.user,
        )
        set_primary_character(self.user, char)
        DiscordUser.objects.create(
            id=1,
            discord_tag="MrUser",
            user=self.user,
        )
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=target_corporation.corporation_id,
            description="Test application",
            discord_thread_id=999,
        )

        with patch("applications.discord.discord") as discord_mock:
            notify_application_transferred(
                application,
                previous_corporation_id=source_corporation.corporation_id,
                transferred_by_username="Recruiter",
            )

            discord_mock.rename_thread.assert_called_once_with(
                channel_id=999,
                name="Mr User - Target Corporation",
            )
            discord_mock.update_message.assert_called_once()
            discord_mock.create_message.assert_called_once()
            message = discord_mock.create_message.call_args.kwargs["message"]
            self.assertIn("Source Corporation", message)
            self.assertIn("Target Corporation", message)
            self.assertIn("Recruiter", message)


class ApplicationPrimeTimeTest(TestCase):
    """Parse application timezone lines onto EvePlayer.prime_time."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        self.client = Client()
        super().setUp()

    def tearDown(self):
        signals.post_save.connect(
            eve_corporation_application_post_save,
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        super().tearDown()

    def test_parse_application_prime_time_from_ustz_label(self):
        description = (
            "Questionnaire:\n"
            "- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n"
            "- Roles interested in: Fleet damage"
        )
        self.assertEqual(parse_application_prime_time(description), "US")

    def test_parse_application_prime_time_compound_labels(self):
        cases = (
            ("USTZ - AUTZ", "US_AP"),
            ("AUTZ - EUTZ", "AP_EU"),
            ("EUTZ - USTZ", "EU_US"),
            ("AUTZ", "AP"),
            ("EUTZ", "EU"),
        )
        for label, code in cases:
            description = f"Questionnaire:\n- Timezone: Asia/Tokyo — AP region, evenings → {label}\n"
            self.assertEqual(
                parse_application_prime_time(description),
                code,
                msg=label,
            )

    def test_parse_application_prime_time_missing_line(self):
        self.assertIsNone(
            parse_application_prime_time("Please accept my application.")
        )

    def test_apply_application_prime_time_sets_player(self):
        EvePlayer.objects.create(user=self.user, nickname="Player One")
        apply_application_prime_time(
            self.user,
            "Questionnaire:\n- Timezone: Europe/London — EU region, evenings → EUTZ\n",
        )
        self.assertEqual(user_player(self.user).prime_time, "EU")

    def test_apply_application_prime_time_skips_missing_player(self):
        apply_application_prime_time(
            self.user,
            "Questionnaire:\n- Timezone: Europe/London — EU region, evenings → EUTZ\n",
        )
        self.assertIsNone(user_player(self.user))

    def test_create_corporation_application_sets_prime_time(self):
        EvePlayer.objects.create(user=self.user, nickname="Player One")
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )
        description = (
            "I want to join.\n\n"
            "Questionnaire:\n"
            "- Timezone: America/New_York (EDT) — US region, evenings → USTZ\n"
            "- Roles interested in: Fleet damage\n"
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            data={"description": description},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user_player(self.user).prime_time, "US")

    def test_create_corporation_application_without_timezone_leaves_prime_time(
        self,
    ):
        player = EvePlayer.objects.create(
            user=self.user,
            nickname="Player One",
            prime_time="AP",
        )
        corporation = EveCorporation.objects.create(
            corporation_id=123,
            name="Test Corporation",
        )

        response = self.client.post(
            f"{BASE_URL}corporations/{corporation.corporation_id}/applications",
            data={"description": "Please accept me."},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertEqual(player.prime_time, "AP")


class ProcessedByDeleteTest(TestCase):
    """processed_by is cleared when that user is deleted; the applicant is not."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        super().setUp()

    def test_deleting_processor_keeps_the_application(self):
        recruiter = User.objects.create(username="recruiter")
        application = EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=98838663,
            description="keep me",
            status="accepted",
            processed_by=recruiter,
            discord_thread_id=1,
        )

        recruiter.delete()

        application.refresh_from_db()
        self.assertIsNone(application.processed_by_id)
        self.assertEqual(application.status, "accepted")
        self.assertEqual(application.user_id, self.user.id)

    def test_deleting_applicant_still_removes_the_application(self):
        applicant = User.objects.create(username="applicant")
        application = EveCorporationApplication.objects.create(
            user=applicant,
            corporation_id=98838663,
            description="gone",
        )
        application_id = application.id

        applicant.delete()

        self.assertFalse(
            EveCorporationApplication.objects.filter(
                pk=application_id
            ).exists()
        )

    def test_restore_migration_inserts_missing_application(self):
        applicant = User.objects.create(id=3094, username="maurdakar")

        restore_deleted_applications(apps, None)

        application = EveCorporationApplication.objects.get(pk=1958)
        self.assertEqual(application.user_id, applicant.id)
        self.assertEqual(application.corporation_id, 98838663)
        self.assertEqual(application.status, "accepted")
        self.assertEqual(application.discord_thread_id, 1533166091159867522)
        self.assertIsNone(application.processed_by_id)
        self.assertTrue(
            application.description.startswith("Mining with MRECK")
        )
        self.assertEqual(
            application.created_at,
            parse_datetime("2026-08-01T17:34:40.981000+00:00"),
        )
        self.assertEqual(
            EveCorporationApplication.objects.filter(
                discord_thread_id=1533166091159867522
            ).count(),
            1,
        )

        restore_deleted_applications(apps, None)

        self.assertEqual(
            EveCorporationApplication.objects.filter(pk=1958).count(), 1
        )


class AcceptApplicationsOfMembersTest(TestCase):
    """Pending applications close once the applicant joins in game."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        super().setUp()
        self.character = EveCharacter.objects.create(
            character_id=1234,
            character_name="Mr User",
            user=self.user,
            corporation_id=1,
        )

    def _apply(self, corporation_id=123, **fields):
        return EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=corporation_id,
            description="Test application",
            **fields,
        )

    @patch("applications.tasks.sync_application_thread_task")
    def test_joining_accepts_and_posts_the_joined_notice(self, sync_mock):
        application = self._apply(discord_thread_id=555)
        accept_applications_of_members_task()
        application.refresh_from_db()
        self.assertEqual(application.status, "pending")

        self.character.corporation_id = 123
        self.character.save()
        accept_applications_of_members_task()

        application.refresh_from_db()
        self.assertEqual(application.status, "accepted")
        self.assertIsNone(application.processed_by_id)
        sync_mock.delay.assert_called_once_with(application.id, "joined")

    def test_an_alt_in_the_corporation_counts(self):
        EveCharacter.objects.create(
            character_id=5678,
            character_name="Mr Alt",
            user=self.user,
            corporation_id=123,
        )
        application = self._apply()

        self.assertEqual(accept_applications_of_members(), [application.id])

    def test_decided_and_other_corporation_applications_stay(self):
        self.character.corporation_id = 123
        self.character.save()
        rejected = self._apply(status="rejected")
        elsewhere = self._apply(corporation_id=456)
        other_user = User.objects.create(username="other")
        theirs = EveCorporationApplication.objects.create(
            user=other_user, corporation_id=789, description="x"
        )
        EveCharacter.objects.create(
            character_id=999, character_name="Other", corporation_id=789
        )

        self.assertEqual(accept_applications_of_members(), [])
        for application, status in (
            (rejected, "rejected"),
            (elsewhere, "pending"),
            (theirs, "pending"),
        ):
            application.refresh_from_db()
            self.assertEqual(application.status, status)

    def test_joined_notice_closes_the_thread(self):
        application = self._apply(discord_thread_id=555)
        with patch("applications.discord.discord") as discord_mock:
            sync_application_thread_task(application.id, "joined")
        message = discord_mock.create_message.call_args.kwargs["message"]
        self.assertIn("joined the corporation", message)
        self.assertNotIn("Apply in-game", message)
        discord_mock.close_thread.assert_called_once_with(channel_id=555)
