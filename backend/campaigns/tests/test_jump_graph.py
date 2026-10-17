"""Operational state from warzone adjacency."""

from django.test import TestCase

from campaigns.models import OperationalState
from campaigns.services import jump_graph
from intel.services import fixtures as intel_fixtures

MINMATAR = 500002
AMARR = 500003

KAMELA = 30003069
KOURMONEN = 30003068


class JumpGraphTests(TestCase):
    def setUp(self):
        jump_graph.load_graph.cache_clear()

    def test_the_fixture_is_present_and_covers_the_warzone(self):
        """Without this fixture no complex can ever be classed with certainty."""
        graph = jump_graph.load_graph()
        self.assertTrue(graph["edges"], "warzone jump graph fixture missing")
        self.assertIn(str(KAMELA), graph["edges"])

    def test_kourmonen_is_a_kamela_neighbour(self):
        self.assertIn(KOURMONEN, jump_graph.neighbours(KAMELA))

    def test_a_system_next_to_the_enemy_is_a_frontline(self):
        owners = {KAMELA: AMARR, KOURMONEN: MINMATAR}
        self.assertEqual(
            jump_graph.classify_system(KAMELA, AMARR, owners),
            OperationalState.FRONTLINE,
        )

    def test_a_system_two_jumps_out_is_command_operations(self):
        owners = {
            KAMELA: MINMATAR,
            KOURMONEN: MINMATAR,
            30003070: AMARR,  # Sosala, next to Kamela
        }
        self.assertEqual(
            jump_graph.classify_system(KOURMONEN, MINMATAR, owners),
            OperationalState.COMMAND,
        )

    def test_without_ownership_the_state_is_unknown_not_guessed(self):
        self.assertEqual(
            jump_graph.classify_system(KAMELA, AMARR, {}),
            OperationalState.UNKNOWN,
        )

    def test_an_unknown_owner_is_unknown(self):
        self.assertEqual(
            jump_graph.classify_system(KAMELA, None, {KAMELA: AMARR}),
            OperationalState.UNKNOWN,
        )


class JumpGraphMatchesIntelMapTests(TestCase):
    """The campaign graph and the desktop intel map come from one SDE.

    They are exported by two commands (``export_warzone_jump_graph`` and
    ``export_intel_fixtures``). Refreshing only one would let campaign
    frontline states and desktop jump counts disagree, so fail instead.
    """

    def setUp(self):
        jump_graph.load_graph.cache_clear()
        intel_fixtures.load_map.cache_clear()

    def test_both_fixtures_come_from_the_same_sde_build(self):
        self.assertEqual(
            jump_graph.load_graph()["source"],
            intel_fixtures.load_map()["source"],
            "Re-run export_warzone_jump_graph and export_intel_fixtures "
            "against the same SDE.",
        )

    def test_warzone_edges_equal_the_intel_map_within_the_warzone(self):
        warzone = jump_graph.load_graph()
        intel = intel_fixtures.load_map()
        self.assertLessEqual(
            set(warzone["region_ids"]), set(intel["region_ids"])
        )
        warzone_ids = set(warzone["systems"])
        self.assertLessEqual(warzone_ids, set(intel["systems"]))
        for system_id, system in warzone["systems"].items():
            self.assertEqual(system["name"], intel["systems"][system_id])
            self.assertEqual(
                sorted(warzone["edges"].get(system_id, [])),
                sorted(
                    neighbour
                    for neighbour in intel["edges"].get(system_id, [])
                    if str(neighbour) in warzone_ids
                ),
                f"edges differ for system {system_id}",
            )
