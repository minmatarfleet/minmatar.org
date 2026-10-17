"""Killmail sync: skip stored mails before fetching."""

from unittest.mock import patch

import factory
from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.helpers.characters.update import update_character_killmails
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
)

ATTACKERS = [
    {
        "character_id": 2,
        "corporation_id": 3,
        "alliance_id": None,
        "faction_id": 500002,
        "ship_type_id": 670,
        "damage_done": 100,
        "final_blow": True,
    },
    {
        "character_id": None,
        "corporation_id": 1000125,
        "alliance_id": None,
        "faction_id": None,
        "ship_type_id": 3740,
        "damage_done": 5,
        "final_blow": False,
    },
]
ITEMS = [
    {
        "flag": 27,
        "item_type_id": 2961,
        "quantity_destroyed": 1,
        "quantity_dropped": None,
        "singleton": 0,
        "items": None,
    }
]


def _detail(killmail_id):
    return EsiResponse(
        response_code=0,
        data={
            "killmail_id": killmail_id,
            "solar_system_id": 30003067,
            "killmail_time": timezone.now(),
            "victim": {
                "character_id": 1001,
                "corporation_id": None,
                "ship_type_id": 587,
                "items": ITEMS,
            },
            "attackers": ATTACKERS,
        },
    )


@factory.django.mute_signals(signals.pre_save, signals.post_save)
class UpdateCharacterKillmailsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.char = EveCharacter.objects.create(
            character_id=1001, character_name="Killmail Pilot"
        )

    def _recent(self, esi, ids):
        esi.get_recent_killmails.return_value = EsiResponse(
            response_code=0,
            data=[{"killmail_id": i, "killmail_hash": f"h{i}"} for i in ids],
        )

    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_stored_killmails_are_not_fetched_again(self, esi_cls):
        esi = esi_cls.return_value
        self._recent(esi, [11, 12])
        esi.get_character_killmail.side_effect = lambda i, h: _detail(i)

        update_character_killmails(self.char.character_id)
        self.assertEqual(esi.get_character_killmail.call_count, 2)

        esi.get_character_killmail.reset_mock()
        self._recent(esi, [11, 12, 13])
        update_character_killmails(self.char.character_id)

        esi.get_character_killmail.assert_called_once_with(13, "h13")
        self.assertEqual(EveCharacterKillmail.objects.count(), 3)
