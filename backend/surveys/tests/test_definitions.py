from django.test import TestCase

from surveys.definitions import SURVEY_DEFINITIONS
from surveys.definitions.core import CORE_BLOCK


class DefinitionRegistryTests(TestCase):
    def test_question_keys_unique_within_each_definition(self):
        for key, definition in SURVEY_DEFINITIONS.items():
            keys = [q.key for q in definition.all_questions()]
            self.assertEqual(
                len(keys), len(set(keys)), f"duplicate keys in {key}"
            )

    def test_core_block_present_and_trendable(self):
        for key, definition in SURVEY_DEFINITIONS.items():
            core_keys = {q.key for q in CORE_BLOCK.questions}
            defn_keys = {q.key for q in definition.all_questions()}
            self.assertTrue(
                core_keys.issubset(defn_keys), f"core missing from {key}"
            )
        # Every core rating question is trendable.
        trendable = {q.key for q in CORE_BLOCK.questions if q.trendable}
        self.assertIn("core.satisfaction", trendable)
        self.assertIn("core.enps", trendable)
