from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter, EveCorporation

URL = "/api/eveonline/corporations/corporations/98726134/page_text"


class CorporationPageTextTestCase(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        self.client = Client()
        ceo = EveCharacter.objects.create(
            character_id=2001, character_name="Ceo", user=self.user
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Rattini Tribe",
            ceo=ceo,
            introduction="Old headline",
            biography="Old about",
        )
        self.director_user = User.objects.create(username="director")
        director = EveCharacter.objects.create(
            character_id=2002,
            character_name="Director",
            user=self.director_user,
        )
        self.corporation.directors.add(director)
        self.member_user = User.objects.create(username="member")

    def call(self, method, user=None, body=None):
        return getattr(self.client, method)(
            URL,
            data=body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(user or self.user)}",
        )

    def test_ceo_and_directors_only(self):
        body = self.call("get").json()
        self.assertEqual("Old headline", body["introduction"])
        self.assertEqual("", body["highlights"])
        self.assertEqual(
            200, self.call("get", user=self.director_user).status_code
        )
        self.assertEqual(
            403, self.call("get", user=self.member_user).status_code
        )
        response = self.call(
            "put", user=self.member_user, body={"introduction": "Hacked"}
        )
        self.assertEqual(403, response.status_code)
        self.corporation.refresh_from_db()
        self.assertEqual("Old headline", self.corporation.introduction)

    def test_director_edits_only_the_fields_sent(self):
        response = self.call(
            "put",
            user=self.director_user,
            body={
                "introduction": "  We kill Amarr.\n  Every day.  ",
                "activity_summary": "## Roams\nDaily.",
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "We kill Amarr. Every day.", response.json()["introduction"]
        )
        self.corporation.refresh_from_db()
        self.assertEqual(
            "We kill Amarr. Every day.", self.corporation.introduction
        )
        self.assertEqual("## Roams\nDaily.", self.corporation.activity_summary)
        self.assertEqual("Old about", self.corporation.biography)

    def test_profanity_saves_nothing(self):
        response = self.call(
            "put",
            body={"introduction": "New headline", "highlights": "No sh1t"},
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            {"detail": "profanity", "field": "highlights", "words": ["shit"]},
            response.json(),
        )
        self.corporation.refresh_from_db()
        self.assertEqual("Old headline", self.corporation.introduction)

    def test_new_text_over_the_limit_is_refused(self):
        response = self.call("put", body={"introduction": "x" * 501})
        self.assertEqual(400, response.status_code)
        self.assertEqual("too_long", response.json()["detail"])
        self.assertEqual("introduction", response.json()["field"])

    def test_long_text_saved_before_the_limit_can_stay(self):
        self.corporation.introduction = "x" * 600
        self.corporation.save()
        response = self.call(
            "put",
            body={"introduction": "x" * 600, "biography": "New about"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("New about", response.json()["biography"])

    def test_public_page_shows_the_new_headline(self):
        self.call("put", body={"introduction": "Fly with Rattini"})
        response = self.client.get(
            "/api/eveonline/corporations/corporations/98726134/info"
        )
        self.assertEqual("Fly with Rattini", response.json()["introduction"])
