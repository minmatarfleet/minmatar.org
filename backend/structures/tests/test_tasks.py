import factory

from django.db.models import signals

from app.test import TestCase

from eveonline.models import EveAlliance, EveCorporation, EveCharacter

from structures.tasks import (
    setup_structure_managers,
    structure_managers_for_minute,
    process_structure_notifications,
)
from structures.models import EveStructureManager
from structures.tests.test_helpers import make_character


class StructureTimerTaskTests(TestCase):
    """Task tests for structure timers"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_setup_structure_managers(self):
        self.assertEqual(0, EveStructureManager.objects.count())

        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
        )
        chars = [
            EveCharacter.objects.create(
                character_id=2001,
                character_name="Director 1",
            ),
            EveCharacter.objects.create(
                character_id=2002,
                character_name="Director 2",
            ),
            EveCharacter.objects.create(
                character_id=2003,
                character_name="CEO",
            ),
        ]

        setup_structure_managers(corp, chars)

        managers = EveStructureManager.objects.all().order_by("poll_time")
        self.assertEqual(3, managers.count())
        self.assertEqual(0, managers[0].poll_time)
        self.assertEqual(3, managers[1].poll_time)
        self.assertEqual(6, managers[2].poll_time)

        minute_3 = structure_managers_for_minute(3)
        self.assertEqual(1, minute_3.count())

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_process_structure_notifications(self):
        scopes = [
            "esi-characters.read_notifications.v1",
            "esi-fleets.read_fleet.v1",
        ]
        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
            alliance=EveAlliance.objects.create(alliance_id=99011978),
        )
        make_character(2001, corp, scopes)
        make_character(2002, corp, [])
        make_character(2003, corp, scopes)
        make_character(2004, corp, scopes)
        make_character(2005, None, scopes)

        self.assertEqual(0, EveStructureManager.objects.count())

        process_structure_notifications()

        self.assertEqual(3, EveStructureManager.objects.count())
