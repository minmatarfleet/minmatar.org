from __future__ import annotations

from django.test import TestCase

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import (
    dominant_attacker_faction,
    resolve_attacker_militia_factions,
)


def _killmail(
    killmail_id: int,
    attackers: list[dict],
) -> dict:
    return {"killmail_id": killmail_id, "attackers": attackers, "victim": {}}


class DominantAttackerFactionTestCase(TestCase):
    def test_majority_minmatar_returns_minmatar(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_MINMATAR,
                    }
                    for i in range(8)
                ]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(2)
                ],
            )
        ]
        self.assertEqual(
            dominant_attacker_faction(killmails),
            FACTION_MINMATAR,
        )

    def test_sixty_percent_minmatar_returns_none(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_MINMATAR,
                    }
                    for i in range(6)
                ]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(4)
                ],
            )
        ]
        self.assertIsNone(dominant_attacker_faction(killmails))

    def test_minority_minmatar_returns_none(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_MINMATAR,
                    }
                    for i in range(4)
                ]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(6)
                ],
            )
        ]
        self.assertIsNone(dominant_attacker_faction(killmails))

    def test_majority_amarr_returns_amarr(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_AMARR,
                    }
                    for i in range(5)
                ]
                + [{"character_id": 200, "faction_id": FACTION_MINMATAR}],
            )
        ]
        self.assertEqual(
            dominant_attacker_faction(killmails),
            FACTION_AMARR,
        )

    def test_militia_tag_without_character_id_does_not_count(self):
        killmails = [
            _killmail(
                1,
                [{"faction_id": FACTION_MINMATAR}]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(9)
                ],
            )
        ]
        self.assertIsNone(dominant_attacker_faction(killmails))

    def test_exact_seventy_five_percent_qualifies(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_MINMATAR,
                    }
                    for i in range(3)
                ]
                + [{"character_id": 200, "faction_id": 500003}],
            )
        ]
        self.assertEqual(
            dominant_attacker_faction(killmails),
            FACTION_MINMATAR,
        )

    def test_below_seventy_five_percent_returns_none(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100 + i,
                        "faction_id": FACTION_MINMATAR,
                    }
                    for i in range(4)
                ]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(4)
                ],
            )
        ]
        self.assertIsNone(dominant_attacker_faction(killmails))

    def test_untagged_pilot_without_affiliation_is_not_inferred(self):
        killmails = [
            _killmail(
                1,
                [
                    {
                        "character_id": 100,
                        "corporation_id": 98000001,
                        "faction_id": FACTION_MINMATAR,
                    },
                    {
                        "character_id": 101,
                        "corporation_id": 98000001,
                    },
                ],
            )
        ]
        factions = resolve_attacker_militia_factions(killmails)
        self.assertEqual(factions.get(100), FACTION_MINMATAR)
        self.assertNotIn(101, factions)
        self.assertIsNone(dominant_attacker_faction(killmails))
