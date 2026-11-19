from unittest.mock import MagicMock, patch

import factory
from django.core.cache import cache
from django.db.models import signals
from esi.models import Scope, Token

from app.test import TestCase
from eveonline import esi_budget
from eveonline.client import EsiResponse
from eveonline.helpers.notifications import (
    NOTIFICATION_SCOPE,
    character_ids_for_minute,
    fetch_notifications,
    store_notifications,
)
from eveonline.models import EveCharacter, EveCharacterNotification
from eveonline.tasks.notifications import (
    fetch_character_notifications,
    poll_character_notifications,
)


@factory.django.mute_signals(signals.pre_save, signals.post_save)
def make_character(character_id, scopes=(NOTIFICATION_SCOPE,), **fields):
    token = Token.objects.create(character_id=character_id)
    for name in scopes:
        token.scopes.add(Scope.objects.get_or_create(name=name)[0])
    return EveCharacter.objects.create(
        character_id=character_id,
        character_name=f"Pilot {character_id}",
        token=token,
        **fields,
    )


def notification(notification_id, kind="StructureLostArmor", **fields):
    return {
        "notification_id": notification_id,
        "type": kind,
        "sender_id": 1000182,
        "sender_type": "corporation",
        "timestamp": "2026-11-19T12:00:00Z",
        "is_read": False,
        "text": "structureID: 1049253339308\n",
        **fields,
    }


class StoreNotificationsTests(TestCase):
    def setUp(self):
        self.character = make_character(2001)

    def test_every_type_is_stored_once(self):
        stored = store_notifications(
            self.character,
            [
                notification(1),
                notification(2, kind="FacWarLPPayoutEvent"),
                notification(3, kind="SomethingCcpAddsNextWeek"),
            ],
        )
        self.assertEqual(3, stored)

        again = store_notifications(
            self.character, [notification(1), notification(4)]
        )
        self.assertEqual(1, again)
        self.assertEqual(4, EveCharacterNotification.objects.count())

        row = EveCharacterNotification.objects.get(notification_id=2)
        self.assertEqual("FacWarLPPayoutEvent", row.type)
        self.assertEqual(1000182, row.sender_id)
        self.assertEqual("corporation", row.sender_type)
        self.assertFalse(row.is_read)
        self.assertEqual(12, row.timestamp.hour)

    def test_junk_is_skipped(self):
        stored = store_notifications(
            self.character,
            [
                None,
                {},
                {"notification_id": "nope", "type": "X", "timestamp": "x"},
                notification(5, timestamp="not a time"),
                notification(6, type=""),
                notification(7, timestamp="2026-11-19 03:16:00+00:00"),
            ],
        )
        self.assertEqual(1, stored)

    def test_the_same_id_for_two_characters_is_two_rows(self):
        other = make_character(2002)
        store_notifications(self.character, [notification(1)])
        store_notifications(other, [notification(1)])
        self.assertEqual(2, EveCharacterNotification.objects.count())


class RosterTests(TestCase):
    def test_each_character_with_the_scope_lands_in_one_minute(self):
        make_character(3001)
        make_character(3011)
        make_character(3002)
        make_character(3003, scopes=["esi-skills.read_skills.v1"])
        make_character(3021, esi_deleted=True)

        self.assertEqual([3001, 3011], character_ids_for_minute(1))
        self.assertEqual([3001, 3011], character_ids_for_minute(21))
        self.assertEqual([3002], character_ids_for_minute(2))
        self.assertEqual([], character_ids_for_minute(3))


class FetchNotificationsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.character = make_character(4001)

    @patch("eveonline.helpers.notifications.EsiClient")
    def test_a_fetch_stores_everything(self, esi):
        esi.return_value.get_character_notifications.return_value = (
            EsiResponse(
                response_code=200,
                data=[notification(1), notification(2, kind="Other")],
            )
        )
        result = fetch_notifications(self.character)
        self.assertEqual({"polled": 1, "stored": 2, "skipped": 0}, result)

    @patch("eveonline.helpers.notifications.EsiClient")
    def test_not_modified_stores_nothing(self, esi):
        response = MagicMock()
        response.response_code = 304
        response.results.side_effect = AssertionError("304 has no body")
        esi.return_value.get_character_notifications.return_value = response
        result = fetch_notifications(self.character)
        self.assertEqual({"polled": 1, "stored": 0, "skipped": 0}, result)

    @patch("eveonline.helpers.notifications.EsiClient")
    def test_rate_limit_pauses_the_character(self, esi):
        http = MagicMock()
        http.headers = {"Retry-After": "90"}
        esi.return_value.get_character_notifications.return_value = (
            EsiResponse(response_code=429, response=http)
        )
        fetch_notifications(self.character)
        self.assertFalse(esi_budget.can_spend("char-notification", 4001))

        # The paused character is not asked again until the pause ends.
        esi.reset_mock()
        result = fetch_notifications(self.character)
        self.assertEqual(1, result["skipped"])
        esi.return_value.get_character_notifications.assert_not_called()

    @patch("eveonline.helpers.notifications.EsiClient")
    def test_an_exception_is_contained(self, esi):
        esi.return_value.get_character_notifications.side_effect = (
            ConnectionError("socket hung up")
        )
        result = fetch_notifications(self.character)
        self.assertEqual(0, result["stored"])
        self.assertLess(esi_budget.error_budget(), 100)


class NotificationTaskTests(TestCase):
    @patch(
        "eveonline.tasks.notifications.get_esi_downtime_countdown",
        return_value=0,
    )
    @patch(
        "eveonline.tasks.notifications.fetch_character_notifications.apply_async"
    )
    def test_the_poll_queues_this_minutes_characters(self, apply_async, _):
        make_character(5005)
        make_character(5006)
        self.assertEqual(1, poll_character_notifications(5))
        apply_async.assert_called_once_with(args=[5005], countdown=0)

    @patch(
        "eveonline.tasks.notifications.get_esi_downtime_countdown",
        return_value=300,
    )
    @patch("eveonline.helpers.notifications.EsiClient")
    @patch(
        "eveonline.tasks.notifications.fetch_character_notifications.apply_async"
    )
    def test_downtime_skips_both_steps(self, apply_async, esi, _):
        make_character(5005)
        self.assertEqual(0, poll_character_notifications(5))
        self.assertEqual(1, fetch_character_notifications(5005)["skipped"])
        apply_async.assert_not_called()
        esi.assert_not_called()
