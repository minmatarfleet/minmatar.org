from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from app.test import TestCase
from access_lists.helpers import (
    get_executor_character,
    sync_access_lists_for_character,
    upsert_access_list,
)
from access_lists.models import (
    AccessLevel,
    EntityType,
    EveAccessList,
    EveAccessListMember,
)
from eveonline.client import EsiResponse
from eveonline.models import EveCharacter

User = get_user_model()

SAMPLE_DETAIL = {
    "name": "Fleet Bookmarks",
    "description": "Shared bookmark ACL",
    "membership": {
        "allow_everyone": False,
        "characters": [
            {"character_id": 1001, "access": "Allowed"},
            {"character_id": 1002, "access": "Manager"},
        ],
        "corporations": [
            {"corporation_id": 2001, "access": "Allowed"},
        ],
        "alliances": [
            {"alliance_id": 3001, "access": "Blocked"},
        ],
    },
}


class AccessListHelperTests(TestCase):
    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.create(
            character_id=424242,
            character_name="BearThatFarms",
            user=self.user,
        )

    def test_get_executor_character_by_name(self):
        found = get_executor_character("BearThatFarms")
        self.assertEqual(found, self.character)

    def test_get_executor_character_by_username(self):
        self.character.character_name = "Other Name"
        self.character.save()
        self.user.username = "bearthatfarms"
        self.user.save()

        found = get_executor_character("BearThatFarms")
        self.assertEqual(found, self.character)

    @patch("access_lists.helpers.requests.post")
    def test_upsert_access_list_stores_members(self, names_post_mock):
        names_post_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": 1001, "name": "Pilot One", "category": "character"},
                {"id": 1002, "name": "Pilot Two", "category": "character"},
                {
                    "id": 2001,
                    "name": "Rattini Tribe",
                    "category": "corporation",
                },
                {
                    "id": 3001,
                    "name": "Minmatar Fleet Alliance",
                    "category": "alliance",
                },
            ],
        )

        access_list = upsert_access_list(self.character, 9001, SAMPLE_DETAIL)

        self.assertEqual(access_list.name, "Fleet Bookmarks")
        self.assertFalse(access_list.allow_everyone)
        self.assertEqual(access_list.members.count(), 4)
        self.assertTrue(
            EveAccessListMember.objects.filter(
                access_list=access_list,
                entity_type=EntityType.CHARACTER,
                entity_id=1001,
                access=AccessLevel.ALLOWED,
                entity_name="Pilot One",
            ).exists()
        )
        self.assertTrue(
            EveAccessListMember.objects.filter(
                access_list=access_list,
                entity_type=EntityType.ALLIANCE,
                entity_id=3001,
                access=AccessLevel.BLOCKED,
            ).exists()
        )

    @patch("access_lists.helpers.esi_for")
    def test_sync_access_lists_for_character(self, esi_for_mock):
        esi = MagicMock()
        esi_for_mock.return_value = esi
        esi.get_character_access_lists.return_value = EsiResponse(
            response_code=0,
            data={"access_lists": [{"id": 9001}, {"id": 9002}]},
        )
        esi.get_character_access_list_detail.side_effect = [
            EsiResponse(response_code=0, data=SAMPLE_DETAIL),
            EsiResponse(
                response_code=0,
                data={
                    "name": "Structure ACL",
                    "description": "",
                    "membership": {
                        "allow_everyone": True,
                        "characters": [],
                        "corporations": [],
                        "alliances": [],
                    },
                },
            ),
        ]

        with patch(
            "access_lists.helpers.upsert_access_list",
            wraps=upsert_access_list,
        ) as upsert_mock:
            with patch(
                "access_lists.helpers.requests.post"
            ) as names_post_mock:
                names_post_mock.return_value = MagicMock(
                    status_code=200,
                    json=lambda: [],
                )
                result = sync_access_lists_for_character(self.character)

        self.assertTrue(result["success"])
        self.assertEqual(result["listed"], 2)
        self.assertEqual(result["synced"], 2)
        self.assertEqual(upsert_mock.call_count, 2)
        self.assertEqual(EveAccessList.objects.count(), 2)

    @patch("access_lists.helpers.esi_for")
    def test_sync_removes_stale_access_lists(self, esi_for_mock):
        stale = EveAccessList.objects.create(
            access_list_id=1,
            name="Old ACL",
            owner_character=self.character,
        )
        EveAccessListMember.objects.create(
            access_list=stale,
            entity_type=EntityType.CHARACTER,
            entity_id=42,
            access=AccessLevel.ALLOWED,
        )

        esi = MagicMock()
        esi_for_mock.return_value = esi
        esi.get_character_access_lists.return_value = EsiResponse(
            response_code=0,
            data={"access_lists": []},
        )

        result = sync_access_lists_for_character(self.character)

        self.assertTrue(result["success"])
        self.assertEqual(result["removed"], 1)
        self.assertFalse(
            EveAccessList.objects.filter(access_list_id=1).exists()
        )

    @patch("access_lists.helpers.esi_for")
    def test_sync_reports_esi_failure(self, esi_for_mock):
        esi = MagicMock()
        esi_for_mock.return_value = esi
        esi.get_character_access_lists.return_value = EsiResponse(
            response_code=905,
        )

        result = sync_access_lists_for_character(self.character)
        self.assertFalse(result["success"])
        self.assertIn("905", result["error"])
