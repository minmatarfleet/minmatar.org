from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from applications.l3arn import (
    L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH,
    L3ARN_CORPORATION_NAME,
    l3arn_discord_description,
    validate_l3arn_application_description,
)
from applications.models import EveCorporationApplication
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from eveonline.helpers.characters import set_primary_character

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

    def test_l3arn_discord_description_strips_how_found_line(self):
        description = (
            "Questionnaire:\n"
            "- Goals in EVE: FW\n"
            "- How I found you: Other (friend)\n"
            "- Other corps considered: none"
        )
        self.assertEqual(
            l3arn_discord_description(description),
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


class EveCorporationApplicationSignalTest(TestCase):
    """Test case for the application signal handlers."""

    def test_application_post_save_signal(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )

        corporation = EveCorporation.objects.create(
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

        with patch("applications.signals.discord") as discord_mock:
            EveCorporationApplication.objects.create(
                user=self.user,
                corporation_id=corporation.corporation_id,
                description="Test application",
                status="accepted",
            )

            discord_mock.create_message.assert_called()
