"""/api/voice: sign-in, status, connect, certificates, FC tools, internal."""

import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from django.test import Client, override_settings
from django.utils import timezone

from app.testing import make_token
from voice import connect, store
from voice.identity import issue_voice_jwt, upsert_identity
from voice.models import (
    MAX_CERTIFICATES,
    VoiceBan,
    VoiceCertificate,
    VoiceConnectToken,
    VoiceGrant,
)
from voice.tests.helpers import VoiceTestCase

BASE = "/api/voice"
SECRET = {"HTTP_X_VOICE_SECRET": "voice-test-secret"}


class VoiceApiTestCase(VoiceTestCase):
    def call(self, method, path, token=None, data=None, **extra):
        kwargs = dict(extra)
        if token:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        if data is not None:
            kwargs["data"] = json.dumps(data)
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(f"{BASE}{path}", **kwargs)


class SignInTest(VoiceApiTestCase):
    @override_settings(ESI_SSO_CLIENT_ID="", ESI_SSO_CALLBACK_URL="")
    def test_login_without_sso_config_says_so(self):
        response = self.call("get", "/login")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=NOT_CONFIGURED", response["Location"])

    @override_settings(
        ESI_SSO_CLIENT_ID="x", ESI_SSO_CALLBACK_URL="https://cb"
    )
    def test_login_asks_eve_for_public_data_only(self):
        with patch("voice.endpoints.get_login.sso_redirect") as sso:
            sso.return_value = __import__(
                "django.http"
            ).http.HttpResponseRedirect("https://login.eveonline.com/")
            self.call("get", "/login?redirect_url=https://evil.example/x")
        self.assertEqual(sso.call_args.kwargs["scopes"], ["publicData"])
        self.assertEqual(
            sso.call_args.kwargs["return_to"], "voice_sso_complete"
        )

    def test_voice_token_is_not_a_site_token(self):
        _, character = self.pilot("guest", user=False)
        identity = self.identity(character)
        response = Client().get(
            "/api/users/me",
            HTTP_AUTHORIZATION=f"Bearer {issue_voice_jwt(identity)}",
        )
        self.assertEqual(response.status_code, 401)

    def test_owner_change_revokes_certificates_and_grants(self):
        identity = upsert_identity(42, "Sold Char", owner_hash="owner-a")
        VoiceCertificate.objects.create(identity=identity, cert_hash="c1")
        fleet = self.fleet()
        VoiceGrant.objects.create(
            character_id=42, fleet=fleet, source=VoiceGrant.SOURCE_CO_FC
        )
        upsert_identity(42, "Sold Char", owner_hash="owner-a")
        self.assertEqual(identity.certificates.count(), 1)
        upsert_identity(42, "Sold Char", owner_hash="owner-b")
        self.assertEqual(identity.certificates.count(), 0)
        self.assertFalse(
            VoiceGrant.objects.filter(expires_at__isnull=True).exists()
        )


class StatusConnectTest(VoiceApiTestCase):
    def test_guest_status_explains_no_access(self):
        _, character = self.pilot("outsider", user=False)
        token = issue_voice_jwt(self.identity(character))
        body = self.call("get", "/status", token).json()
        self.assertFalse(body["admitted"])
        self.assertEqual(body["reason"], "no_access")
        self.assertEqual(body["signed_in_as"], "guest")
        response = self.call("post", "/connect", token, {})
        self.assertEqual(response.status_code, 403)

    def test_member_picks_one_of_their_characters(self):
        user, character = self.pilot("member", "Alliance")
        body = self.call(
            "get",
            f"/status?character_id={character.character_id}",
            make_token(user),
        ).json()
        self.assertTrue(body["admitted"])
        self.assertTrue(body["community"])
        self.assertEqual(body["signed_in_as"], "member")
        self.assertEqual(
            [c["character_id"] for c in body["characters"]],
            [character.character_id],
        )

    def test_member_cannot_pick_someone_elses_character(self):
        user, _ = self.pilot("member", "Alliance")
        _, other = self.pilot("other", "Alliance")
        response = self.call(
            "get",
            f"/status?character_id={other.character_id}",
            make_token(user),
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(VOICE_HOST="voice.example", VOICE_PORT=64738)
    def test_connect_returns_a_one_time_mumble_link(self):
        user, character = self.pilot("O'Neil Test", "Alliance")
        body = self.call("post", "/connect", make_token(user), {}).json()
        parts = urlsplit(body["url"])
        self.assertEqual(parts.scheme, "mumble")
        self.assertEqual(parts.hostname, "voice.example")
        self.assertEqual(parts.port, 64738)
        self.assertEqual(unquote(parts.username), "O'Neil Test")
        self.assertIn("title=Minmatar%20Fleet", body["url"])
        self.assertEqual(body["expires_in_seconds"], 120)
        token = unquote(parts.password)
        row = VoiceConnectToken.objects.get()
        self.assertNotEqual(row.token_hash, token)  # stored hashed
        self.assertEqual(row.token_hash, connect.hash_token(token))
        # Connect also publishes the record for the voice service.
        self.assertIsNotNone(
            store.memory_store().get(
                store.CHAR_KEY.format(character.character_id)
            )
        )


class RedeemTest(VoiceApiTestCase):
    def setUp(self):
        super().setUp()
        _, self.character = self.pilot("pilot", "Alliance")
        self.identity_ = self.identity(self.character)

    def redeem(self, password, cert_hash="", headers=None):
        headers = SECRET if headers is None else headers
        return self.call(
            "post",
            "/internal/redeem",
            data={"password": password, "cert_hash": cert_hash},
            **headers,
        )

    def test_internal_paths_need_the_secret(self):
        token = connect.mint_token(self.identity_)
        self.assertEqual(self.redeem(token, headers={}).status_code, 401)
        self.assertEqual(
            self.redeem(
                token, headers={"HTTP_X_VOICE_SECRET": "wrong"}
            ).status_code,
            401,
        )
        with override_settings(VOICE_INTERNAL_SECRET=""):
            self.assertEqual(self.redeem(token).status_code, 401)

    def test_internal_paths_are_not_in_the_public_schema(self):
        schema = Client().get("/api/openapi.json").json()
        self.assertFalse(
            [p for p in schema["paths"] if "/voice/internal" in p]
        )

    def test_token_binds_the_certificate_once(self):
        token = connect.mint_token(self.identity_)
        response = self.redeem(token, "cert-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["character_id"], self.character.character_id
        )
        self.assertTrue(
            VoiceCertificate.objects.filter(cert_hash="cert-1").exists()
        )
        # Spent.
        self.assertEqual(self.redeem(token, "cert-1").status_code, 404)

    def test_empty_certificate_hash_is_never_bound(self):
        token = connect.mint_token(self.identity_)
        self.assertEqual(self.redeem(token, "").status_code, 200)
        self.assertFalse(VoiceCertificate.objects.exists())
        lookup = self.call(
            "post", "/internal/lookup", data={"cert_hash": ""}, **SECRET
        )
        self.assertEqual(lookup.status_code, 404)

    def test_expired_token_is_refused(self):
        token = connect.mint_token(self.identity_)
        VoiceConnectToken.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.redeem(token).status_code, 404)

    def test_a_certificate_bound_to_someone_else_is_refused(self):
        _, other = self.pilot("other", "Alliance")
        VoiceCertificate.objects.create(
            identity=self.identity(other), cert_hash="theirs"
        )
        token = connect.mint_token(self.identity_)
        self.assertEqual(self.redeem(token, "theirs").status_code, 404)

    def test_at_most_three_certificates(self):
        for n in range(MAX_CERTIFICATES + 1):
            self.assertEqual(
                self.redeem(
                    connect.mint_token(self.identity_), f"c{n}"
                ).status_code,
                200,
            )
        self.assertEqual(self.identity_.certificates.count(), MAX_CERTIFICATES)

    def test_lookup_by_certificate(self):
        VoiceCertificate.objects.create(
            identity=self.identity_, cert_hash="known"
        )
        response = self.call(
            "post", "/internal/lookup", data={"cert_hash": "known"}, **SECRET
        )
        self.assertEqual(response.json()["identity_id"], self.identity_.id)


class FleetToolsTest(VoiceApiTestCase):
    def setUp(self):
        super().setUp()
        self.fc_user, _ = self.pilot("fc", "Alliance")
        self.pilot_user, self.pilot_char = self.pilot("line", "Alliance")
        self.fleet_ = self.fleet(self.fc_user)
        self.lease(self.fleet_, branch=2)
        perm = __import__(
            "django.contrib.auth.models", fromlist=["Permission"]
        ).Permission.objects.get(codename="view_evefleet")
        for user in (self.fc_user, self.pilot_user):
            user.user_permissions.add(perm)

    def test_fc_sees_the_branch_others_do_not_manage(self):
        body = self.call(
            "get", f"/fleets/{self.fleet_.id}", make_token(self.fc_user)
        ).json()
        self.assertTrue(body["can_manage_voice"])
        self.assertEqual(body["branch_name"], "Fleet 2")
        body = self.call(
            "get", f"/fleets/{self.fleet_.id}", make_token(self.pilot_user)
        ).json()
        self.assertFalse(body["can_manage_voice"])
        self.assertIsNone(body["branch"])

    def test_co_fc_add_and_remove(self):
        cid = self.pilot_char.character_id
        path = f"/fleets/{self.fleet_.id}/co-fcs"
        self.assertEqual(
            self.call(
                "post",
                path,
                make_token(self.pilot_user),
                {"character_id": cid},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.call(
                "post", path, make_token(self.fc_user), {"character_id": cid}
            ).status_code,
            204,
        )
        grant = VoiceGrant.objects.get(character_id=cid)
        self.assertEqual(grant.role, VoiceGrant.ROLE_COMMANDER)
        self.call("delete", f"{path}/{cid}", make_token(self.fc_user))
        grant.refresh_from_db()
        self.assertIsNotNone(grant.expires_at)

    def test_wing_mapping_rejects_unknown_channels(self):
        path = f"/fleets/{self.fleet_.id}/wings"
        bad = self.call(
            "post",
            path,
            make_token(self.fc_user),
            {"wing_channels": {"1": "Command"}},
        )
        self.assertEqual(bad.status_code, 400)
        ok = self.call(
            "post",
            path,
            make_token(self.fc_user),
            {"wing_channels": {"1": "Auxiliary A"}},
        )
        self.assertEqual(ok.status_code, 204)

    def test_kick_queues_a_command_and_ends_fleet_access(self):
        identity = self.identity(self.pilot_char)
        VoiceGrant.objects.create(
            character_id=self.pilot_char.character_id,
            fleet=self.fleet_,
            source=VoiceGrant.SOURCE_IN_FLEET,
        )
        response = self.call(
            "post",
            f"/fleets/{self.fleet_.id}/kick",
            make_token(self.fc_user),
            {"character_id": self.pilot_char.character_id},
        )
        self.assertEqual(response.status_code, 204)
        command = json.loads(
            store.memory_store().lrange(store.COMMANDS_KEY, 0, -1)[0]
        )
        self.assertEqual(command["identity_id"], identity.id)
        self.assertFalse(
            VoiceGrant.objects.filter(expires_at__isnull=True).exists()
        )

    def test_only_voice_admins_ban(self):
        data = {"character_id": self.pilot_char.character_id, "reason": "spam"}
        self.assertEqual(
            self.call(
                "post", "/bans", make_token(self.fc_user), data
            ).status_code,
            403,
        )
        self.fc_user.is_superuser = True
        self.fc_user.save()
        self.assertEqual(
            self.call(
                "post", "/bans", make_token(self.fc_user), data
            ).status_code,
            201,
        )
        self.assertTrue(VoiceBan.active().exists())
