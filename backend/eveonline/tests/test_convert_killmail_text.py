import json
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from app.test import TestCase
from eveonline.management.commands.convert_killmail_text_to_json import (
    convert_killmail_text,
)
from eveonline.models import EveCharacter, EveCharacterKillmail

ATTACKERS = [{"character_id": None, "final_blow": True, "damage_done": 3}]
ITEMS = [{"item_type_id": 2961, "quantity_dropped": None, "items": []}]


class ConvertKillmailTextTest(TestCase):
    def setUp(self):
        super().setUp()
        self.char = EveCharacter.objects.create(
            character_id=7001, character_name="Converter"
        )

    def _killmail(self, killmail_id, attackers, items):
        return EveCharacterKillmail.objects.create(
            id=killmail_id,
            killmail_id=killmail_id,
            killmail_hash="h",
            killmail_time=timezone.now(),
            solar_system_id=30003067,
            ship_type_id=587,
            attackers=attackers,
            items=items,
            character=self.char,
        )

    def test_converts_repr_rows_in_batches_and_back(self):
        for killmail_id in range(1, 8):
            self._killmail(killmail_id, str(ATTACKERS), str(ITEMS))
        self._killmail(50, json.dumps(ATTACKERS), json.dumps(ITEMS))
        self._killmail(60, "list of attackers", str(ITEMS))
        before = {
            k.id: (k.attackers, k.items, k.updated_at)
            for k in EveCharacterKillmail.objects.all()
        }

        stats = convert_killmail_text(batch_size=3)

        self.assertEqual(stats["scanned"], 9)
        self.assertEqual(stats["updated"], 8)
        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats["unreadable"], 1)
        for killmail in EveCharacterKillmail.objects.exclude(id=60):
            self.assertEqual(json.loads(killmail.attackers), ATTACKERS)
            self.assertEqual(json.loads(killmail.items), ITEMS)
            self.assertEqual(killmail.updated_at, before[killmail.id][2])
        bad = EveCharacterKillmail.objects.get(id=60)
        self.assertEqual(bad.attackers, "list of attackers")
        self.assertEqual(json.loads(bad.items), ITEMS)

        self.assertEqual(convert_killmail_text(batch_size=3)["updated"], 0)

        convert_killmail_text(reverse=True, batch_size=4)
        for killmail in EveCharacterKillmail.objects.exclude(id=50):
            self.assertEqual(
                (killmail.attackers, killmail.items),
                before[killmail.id][:2],
            )

    def test_dry_run_writes_nothing(self):
        self._killmail(1, str(ATTACKERS), str(ITEMS))
        out = StringIO()
        call_command("convert_killmail_text_to_json", "--dry-run", stdout=out)
        self.assertIn("Would convert 1 of 1", out.getvalue())
        self.assertEqual(
            EveCharacterKillmail.objects.get(id=1).attackers, str(ATTACKERS)
        )

    def test_limit_stops_early(self):
        for killmail_id in range(1, 6):
            self._killmail(killmail_id, str(ATTACKERS), str(ITEMS))
        stats = convert_killmail_text(batch_size=2, limit=3)
        self.assertEqual(stats["scanned"], 3)
        self.assertEqual(
            EveCharacterKillmail.objects.get(id=4).items, str(ITEMS)
        )
