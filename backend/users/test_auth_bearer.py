"""AuthBearer: 401 for bad tokens, never for server errors."""

from unittest.mock import patch

import jwt
from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import Client, RequestFactory, TestCase

from authentication import AuthBearer
from users.jwt_auth import encode_jwt


class AuthBearerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="member")
        self.request = RequestFactory().get("/")
        self.bearer = AuthBearer()

    def test_valid_token_sets_user(self):
        token = encode_jwt({"user_id": self.user.id})
        self.assertEqual(
            self.bearer.authenticate(self.request, token), self.user
        )
        self.assertEqual(self.request.user, self.user)

    def test_bad_tokens_are_401(self):
        forged = jwt.encode(
            {"user_id": self.user.id}, "not-the-key", algorithm="HS256"
        )
        for token in ("garbage", "", forged):
            with self.subTest(token=token):
                self.assertIsNone(
                    self.bearer.authenticate(self.request, token)
                )

    def test_character_only_token_is_401(self):
        token = encode_jwt({"character_id": 9001, "sub": "9001"})
        self.assertIsNone(self.bearer.authenticate(self.request, token))

    def test_unknown_or_malformed_user_is_401(self):
        for user_id in (999999, "abc"):
            with self.subTest(user_id=user_id):
                token = encode_jwt({"user_id": user_id})
                self.assertIsNone(
                    self.bearer.authenticate(self.request, token)
                )

    def test_rejections_are_logged_not_printed(self):
        with patch("builtins.print") as printed, self.assertLogs(
            "authentication", level="DEBUG"
        ) as logs:
            self.bearer.authenticate(self.request, "garbage")
        printed.assert_not_called()
        self.assertIn("Bearer token rejected", logs.output[0])

    def test_database_error_is_not_swallowed(self):
        token = encode_jwt({"user_id": self.user.id})
        with patch.object(
            User.objects, "get", side_effect=OperationalError("db down")
        ):
            with self.assertRaises(OperationalError):
                self.bearer.authenticate(self.request, token)

    def test_database_error_is_a_500_not_a_401(self):
        token = encode_jwt({"user_id": self.user.id})
        client = Client(raise_request_exception=False)
        with patch.object(
            User.objects, "get", side_effect=OperationalError("db down")
        ), self.assertLogs("django.request", level="ERROR"):
            response = client.post(
                "/api/discord/guilds/sync",
                {"guilds": []},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
        self.assertEqual(response.status_code, 500)

    def test_bad_token_on_endpoint_is_still_401(self):
        response = Client().post(
            "/api/discord/guilds/sync",
            {"guilds": []},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer garbage",
        )
        self.assertEqual(response.status_code, 401)
