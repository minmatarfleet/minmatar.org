from django.test import SimpleTestCase

from app import contracts
from reminders.messages.rat_quotes import rat_quotes


class RatBibleContractTest(SimpleTestCase):
    """The Rat Chronicle on the website opens each chapter with a verse of the
    Rat Bible, and its tests read the verses from this committed copy (the
    website's CI does not check out the backend). After changing a verse:

        UPDATE_CONTRACTS=1 python manage.py test reminders.tests.test_rat_bible_contract

    and commit the file. A chapter that quoted the old wording then fails the
    website's tests until its epigraph is updated.
    """

    def test_committed_verses_are_current(self):
        contracts.check(
            self, contracts.WEB / "rat_bible.json", {"verses": rat_quotes}
        )

    def test_every_verse_is_a_citation_and_a_quote(self):
        for verse in rat_quotes:
            self.assertIn(" - '", verse)
            self.assertTrue(verse.endswith("'"), verse)
