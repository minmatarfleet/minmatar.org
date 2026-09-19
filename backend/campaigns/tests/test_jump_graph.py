"""Operational state from warzone adjacency."""

from django.test import TestCase

from campaigns.models import OperationalState
from campaigns.services import jump_graph

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
