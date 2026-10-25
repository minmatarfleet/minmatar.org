"""Training plan order and times, on plain dicts."""

from django.test import SimpleTestCase

from capabilities.engine import rules
from capabilities.engine.plan import Step, eve_text, plan, step_days
from capabilities.engine.requirements import SP_TOTAL

BASE, CHILD, OTHER = 1, 2, 3
RANKS = {BASE: 1.0, CHILD: 5.0, OTHER: 1.0}
PREREQUISITES = {CHILD: {BASE: 3}}


class PlanTest(SimpleTestCase):
    def test_prerequisites_and_lower_levels_go_first(self):
        steps = plan({CHILD: 2}, {}, RANKS, PREREQUISITES)
        order = [(s.skill, s.level) for s in steps]
        self.assertEqual(
            order, [(BASE, 1), (BASE, 2), (BASE, 3), (CHILD, 1), (CHILD, 2)]
        )

    def test_the_cheapest_step_comes_first_when_free(self):
        steps = plan({CHILD: 1, OTHER: 1}, {BASE: 3}, RANKS, PREREQUISITES)
        self.assertEqual(steps[0].skill, OTHER)

    def test_trained_levels_are_skipped(self):
        steps = plan({BASE: 4}, {BASE: 3}, RANKS, {})
        self.assertEqual([(s.skill, s.level) for s in steps], [(BASE, 4)])

    def test_skill_points_already_in_a_level_count(self):
        full = step_days(1.0, 4)
        half = SP_TOTAL[3] + (SP_TOTAL[4] - SP_TOTAL[3]) // 2
        self.assertAlmostEqual(step_days(1.0, 4, half), full / 2, places=2)
        steps = plan({BASE: 4}, {BASE: 3}, RANKS, {}, {BASE: half})
        self.assertAlmostEqual(steps[0].days, round(full / 2, 2), places=2)

    def test_days_follow_the_rank(self):
        sp = (SP_TOTAL[1] - SP_TOTAL[0]) * 5
        self.assertAlmostEqual(step_days(5.0, 1), sp / rules.SP_PER_HOUR / 24)

    def test_eve_text_has_one_line_per_level(self):
        text = eve_text(
            [Step(BASE, 4, 1), Step(BASE, 5, 2)], {BASE: "Mechanics"}
        )
        self.assertEqual(text, "Mechanics IV\nMechanics V")
