from __future__ import annotations

from django.test import TestCase

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.killmail_classify import dominant_attacker_faction


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
                    for i in range(6)
                ]
                + [
                    {"character_id": 200 + i, "faction_id": 500003}
                    for i in range(4)
                ],
            )
        ]
        self.assertEqual(
            dominant_attacker_faction(killmails),
            FACTION_MINMATAR,
        )

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

    def test_exact_half_is_not_a_majority(self):
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
