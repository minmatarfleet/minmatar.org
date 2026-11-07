from unittest import TestCase

from app.profanity import contains_profanity, find_profanity


class ProfanityTests(TestCase):
    def test_finds_profanity_and_its_disguises(self):
        for text, word in (
            ("Fuck this", "fuck"),
            ("FUCKING", "fucking"),
            ("sh1t happens", "shit"),
            ("$hit", "shit"),
            ("b!tch", "bitch"),
            ("f.u.c.k", "fuck"),
            ("f u c k off", "fuck"),
            ("fuuuuuck", "fuck"),
            ("We are dicks", "dick"),
            ("clusterfuck", "fuck"),
            ("bullshitting", "shit"),
            ("fck", "fck"),
            ("f\u200bu\u200bck", "fuck"),
            ("fսck", "fuck"),  # Armenian u
            ("fúck", "fuck"),
            ("a55hole", "asshole"),
            ("blow job", "blow job"),
            ("retard", "retard"),
            ("wtf", "wtf"),
            ("damn", "damn"),
        ):
            with self.subTest(text=text):
                self.assertIn(word, find_profanity(text))

    def test_eve_and_everyday_words_pass(self):
        for text in (
            "We gank and kill Amarr in Amamake.",
            "Free the slaves; slavers die.",
            "Snuffed Out dropped on us.",
            "Sniper doctrine with thrust bonuses.",
            "Strip miners and a hell of a fleet!",
            "Assassins assess the class of Assault frigates.",
            "Bass, grass, passes, hassle, Massive fleets.",
            "Analysis, therapist, grape, Cockpit, Dickens, Hitchcock.",
            "Scunthorpe, Yoshito, Toshitaka, Matsushita, shiitake.",
            "Titles, cumulative, Sussex, consult.",
            "Fly with us! 1v1 duels, 500m ISK SRP, 24/7.",
            "a b c d",
            "",
        ):
            with self.subTest(text=text):
                self.assertEqual([], find_profanity(text))

    def test_reports_each_word_once_in_order(self):
        self.assertEqual(["shit", "fuck"], find_profanity("shit, fuck, SHIT"))
        self.assertTrue(contains_profanity("cunt"))
        self.assertFalse(contains_profanity("Rattini Tribe"))
