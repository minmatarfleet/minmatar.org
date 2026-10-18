"""
Token issuance lives in users.jwt_auth.

The parity tests pin every token to the bytes the pre-refactor encoders
produced, so moving the encoders into one module changed nothing a client
can see.
"""

import datetime
import re
from pathlib import Path
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from esi.models import Token

from authentication import make_test_user
from discord.models import DiscordUser
from eveonline.models import EveCharacter
from users.eve_sso import issue_mobile_jwt
from users.jwt_auth import (
    decode_user_jwt,
    encode_jwt,
    issue_discord_user_jwt,
    issue_fake_login_jwt,
)

FROZEN_NOW = datetime.datetime(
    2026, 10, 17, 12, 0, 0, tzinfo=datetime.timezone.utc
)
BACKEND_ROOT = Path(__file__).resolve().parent.parent


# Verbatim copies of the encoders as they were before the refactor.


def legacy_discord_jwt(request, django_user, discord_user_data):
    payload = {
        "user_id": django_user.id,
        "username": discord_user_data["username"],
        "avatar": (
            f"https://cdn.discordapp.com/avatars/"
            f"{django_user.discord_user.id}/{django_user.discord_user.avatar}.png"
        ),
        "is_superuser": django_user.is_superuser,
        "sub": discord_user_data["username"],
        "iss": request.get_host(),
        "iat": FROZEN_NOW,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def legacy_mobile_jwt(request, esi_token, linked_user):
    payload = {
        "character_id": esi_token.character_id,
        "character_name": esi_token.character_name,
        "avatar": (
            f"https://images.evetech.net/characters/"
            f"{esi_token.character_id}/portrait?size=128"
        ),
        "sub": str(esi_token.character_id),
        "iss": request.get_host(),
        "iat": FROZEN_NOW,
    }
    if linked_user is not None:
        payload.update(
            {
                "user_id": linked_user.id,
                "username": linked_user.username,
                "is_superuser": linked_user.is_superuser,
                "sub": linked_user.username,
            }
        )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def legacy_fake_login_jwt(request, django_user):
    payload = {
        "user_id": django_user.id,
        "username": django_user.username,
        "is_superuser": django_user.is_superuser,
        "sub": django_user.username,
        "iss": request.get_host(),
        "iat": FROZEN_NOW,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class TokenParityTest(TestCase):
    def setUp(self):
        frozen = patch("django.utils.timezone.now", return_value=FROZEN_NOW)
        frozen.start()
        self.addCleanup(frozen.stop)
        self.request = RequestFactory().get("/", HTTP_HOST="api.example.org")
        self.user = User.objects.create(username="Pilot", is_superuser=False)

    def assert_same_token(self, new, old):
        self.assertEqual(new, old)
        self.assertEqual(decode_user_jwt(new), decode_user_jwt(old))

    def test_discord_login_token(self):
        DiscordUser.objects.create(
            id=1234, user=self.user, discord_tag="pilot#0", avatar="abc"
        )
        data = {"username": "pilot"}
        self.assert_same_token(
            issue_discord_user_jwt(self.request, self.user, data),
            legacy_discord_jwt(self.request, self.user, data),
        )

    def test_mobile_token_for_unlinked_character(self):
        esi_token = Token.objects.create(
            character_id=9001, character_name="Loner"
        )
        token = issue_mobile_jwt(self.request, esi_token)
        self.assert_same_token(
            token, legacy_mobile_jwt(self.request, esi_token, None)
        )
        self.assertNotIn("user_id", decode_user_jwt(token))

    def test_mobile_token_for_linked_character(self):
        esi_token = Token.objects.create(
            character_id=9002, character_name="Linked"
        )
        EveCharacter.objects.create(
            character_id=9002, character_name="Linked", user=self.user
        )
        token = issue_mobile_jwt(self.request, esi_token)
        self.assert_same_token(
            token, legacy_mobile_jwt(self.request, esi_token, self.user)
        )
        esi_token.refresh_from_db()
        self.assertEqual(esi_token.user_id, self.user.id)

    def test_fake_login_token(self):
        self.assert_same_token(
            issue_fake_login_jwt(self.request, self.user),
            legacy_fake_login_jwt(self.request, self.user),
        )

    def test_test_helper_tokens(self):
        payload = {"user_id": 7, "username": "x", "is_superuser": True}
        self.assertEqual(
            encode_jwt(payload),
            jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256"),
        )
        with patch("builtins.print") as printed:
            make_test_user(77, "Printed", False)
        legacy = jwt.encode(
            {"user_id": 77, "username": "Printed", "is_superuser": False},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        self.assertIn(legacy, printed.call_args[0][0])

    def test_tokens_still_carry_no_exp(self):
        token = issue_fake_login_jwt(self.request, self.user)
        self.assertNotIn("exp", decode_user_jwt(token))


class SingleTokenModuleTest(TestCase):
    """Only users/jwt_auth.py signs or reads tokens outside of tests."""

    def test_no_other_module_calls_pyjwt(self):
        pattern = re.compile(r"\bjwt\.(encode|decode)\(")
        offenders = []
        for path in BACKEND_ROOT.rglob("*.py"):
            rel = path.relative_to(BACKEND_ROOT)
            parts = rel.parts
            if rel == Path("users/jwt_auth.py"):
                continue
            if any(p.startswith("test") for p in parts):
                continue
            if "migrations" in parts or ".venv" in parts:
                continue
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(rel))
        self.assertEqual(offenders, [])
