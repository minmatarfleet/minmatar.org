"""EVE SSO login only signs in the site user whose EVE account owns the
character."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client
from esi.models import CallbackRedirect, Token

from app.test import TestCase
from eveonline.models import EveCharacter

COMPLETE_URL = "/api/users/eve/complete/"
CHARACTER_ID = 634915984


class EveLoginOwnerTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )
        self.client = Client()
        super().setUp()

    def link_character(self, owner_hash: str | None) -> EveCharacter:
        linked_token = None
        if owner_hash is not None:
            linked_token = Token.objects.create(
                character_id=CHARACTER_ID,
                character_name="Linked Pilot",
                character_owner_hash=owner_hash,
                user=self.user,
            )
        return EveCharacter.objects.create(
            character_id=CHARACTER_ID,
            character_name="Linked Pilot",
            token=linked_token,
            user=self.user,
        )

    def complete_login(self, owner_hash: str):
        sso_token = Token.objects.create(
            character_id=CHARACTER_ID,
            character_name="Linked Pilot",
            character_owner_hash=owner_hash,
        )
        session = self.client.session
        session["authentication_redirect_url"] = "mobile://auth/callback"
        session.save()
        CallbackRedirect.objects.create(
            session_key=session.session_key,
            state="owner-state",
            url=COMPLETE_URL,
            token=sso_token,
        )
        return sso_token, self.client.get(COMPLETE_URL)

    def jwt_payload(self, response) -> dict:
        self.assertIn("mobile://auth/callback?token=", response.url)
        token = response.url.split("?token=", 1)[1]
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

    def assert_refused(self, response, sso_token, code):
        self.assertEqual(302, response.status_code)
        self.assertNotIn("token=", response.url)
        self.assertIn(f"error={code}", response.url)
        self.assertFalse(Token.objects.filter(pk=sso_token.pk).exists())

    def test_matching_owner_hash_signs_in_as_the_linked_user(self):
        self.link_character("owner-a")

        sso_token, response = self.complete_login("owner-a")

        self.assertEqual(302, response.status_code)
        payload = self.jwt_payload(response)
        self.assertEqual(self.user.id, payload["user_id"])
        self.assertEqual(CHARACTER_ID, payload["character_id"])
        sso_token.refresh_from_db()
        self.assertEqual(self.user, sso_token.user)

    def test_different_owner_hash_is_refused(self):
        character = self.link_character("owner-a")

        sso_token, response = self.complete_login("owner-b")

        self.assert_refused(response, sso_token, "CHARACTER_OWNER_CHANGED")
        character.refresh_from_db()
        self.assertEqual(self.user, character.user)
        self.assertEqual("owner-a", character.token.character_owner_hash)

    def test_linked_character_without_token_is_refused(self):
        self.link_character(None)

        sso_token, response = self.complete_login("owner-a")

        self.assert_refused(response, sso_token, "CHARACTER_NOT_VERIFIED")

    def test_linked_token_without_owner_hash_is_refused(self):
        self.link_character("")

        sso_token, response = self.complete_login("owner-a")

        self.assert_refused(response, sso_token, "CHARACTER_NOT_VERIFIED")

    def test_unlinked_character_still_gets_a_character_session(self):
        EveCharacter.objects.create(
            character_id=CHARACTER_ID, character_name="Linked Pilot"
        )

        _, response = self.complete_login("owner-b")

        payload = self.jwt_payload(response)
        self.assertEqual(CHARACTER_ID, payload["character_id"])
        self.assertNotIn("user_id", payload)

    def test_owner_hash_is_checked_against_the_linked_token_only(self):
        """A token another site user holds for the character proves nothing
        about the linked user's ownership."""
        self.link_character("owner-a")
        other = User.objects.create_user(username="other-holder")
        Token.objects.create(
            character_id=CHARACTER_ID,
            character_name="Linked Pilot",
            character_owner_hash="owner-b",
            user=other,
        )

        sso_token, response = self.complete_login("owner-b")

        self.assert_refused(response, sso_token, "CHARACTER_OWNER_CHANGED")
