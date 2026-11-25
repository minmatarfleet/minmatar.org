"""/api/voice: sign-in, status, connect, certificates, FC tools, internal."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

from django.test import Client, RequestFactory, override_settings
from django.utils import timezone

from app.testing import make_token
from eveonline.helpers.characters import set_primary_character
from voice import connect, store
from voice.identity import issue_voice_jwt, upsert_identity
from voice.tasks import publish_fleet_wing_pilots
from voice.views import SESSION_KEY, STATE_SESSION_KEY, voice_sso_complete
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

    @override_settings(
        ESI_SSO_CLIENT_ID="x", ESI_SSO_CALLBACK_URL="https://cb"
    )
    def test_login_keeps_a_well_formed_state_only(self):
        client = Client()
        with patch("voice.endpoints.get_login.sso_redirect") as sso:
            sso.return_value = __import__(
                "django.http"
            ).http.HttpResponseRedirect("https://login.eveonline.com/")
            state = "a" * 43
            client.get(f"{BASE}/login?state={state}")
            self.assertEqual(client.session[STATE_SESSION_KEY], "a" * 43)
            client.get(f"{BASE}/login?state=short")
            self.assertEqual(client.session[STATE_SESSION_KEY], "")

    def test_sign_in_returns_the_state_with_the_token(self):
        _, character = self.pilot("guest", user=False)
        request = RequestFactory().get("/api/voice/complete/")
        request.session = {
            SESSION_KEY: "https://my.minmatar.org/voice/login",
            STATE_SESSION_KEY: "s" * 43,
        }
        token = SimpleNamespace(
            character_id=character.character_id,
            character_name=character.character_name,
            character_owner_hash="owner",
            user_id=None,
            delete=lambda: None,
        )
        with patch(
            "voice.views._public_affiliation", return_value=(None, None)
        ):
            response = voice_sso_complete.__wrapped__(request, token)
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(query["state"], ["s" * 43])
        self.assertTrue(query["token"][0])

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

    def test_a_member_always_connects_as_their_main(self):
        user, main = self.pilot("member", "Alliance")
        alt = self.alt(user, "member alt")
        body = self.call(
            "get",
            f"/status?character_id={alt.character_id}",
            make_token(user),
        ).json()
        self.assertEqual(body["character_id"], main.character_id)
        self.assertTrue(body["admitted"])
        self.assertTrue(body["community"])
        self.assertEqual(body["signed_in_as"], "member")
        self.assertNotIn("characters", body)

    def test_an_alt_signed_in_with_eve_is_refused(self):
        user, _ = self.pilot("member", "Alliance")
        alt = self.alt(user, "member alt")
        token = issue_voice_jwt(self.identity(alt))
        body = self.call("get", "/status", token).json()
        self.assertFalse(body["admitted"])
        self.assertEqual(body["reason"], "not_main")
        self.assertEqual(self.call("post", "/connect", token).status_code, 403)

    def test_status_names_the_fleets_a_pilot_can_join(self):
        fc_user, fc = self.pilot("Liam Varn", "Alliance")
        _, guest = self.pilot("guest", user=False)
        fleet = self.fleet(fc_user, objective="Amamake defence")
        self.lease(fleet, branch=1)
        VoiceGrant.objects.create(
            character_id=guest.character_id,
            fleet=fleet,
            source=VoiceGrant.SOURCE_VOLUNTEER,
        )
        token = issue_voice_jwt(self.identity(guest))
        (access,) = self.call("get", "/status", token).json()["fleets"]
        self.assertEqual(access["fleet_title"], "Amamake defence")
        self.assertEqual(access["fc_name"], fc.character_name)
        self.assertIsNotNone(access["start_time"])
        self.assertEqual(access["branch_name"], "Fleet 1")

    def test_standing_access_does_not_name_the_fleet(self):
        fc_user, _ = self.pilot("Liam Varn", "Alliance")
        _, guest = self.pilot("guest", user=False)
        fleet = self.fleet(fc_user, objective="Amamake defence")
        self.lease(fleet, branch=1)
        VoiceGrant.objects.create(
            character_id=guest.character_id,
            fleet=fleet,
            source=VoiceGrant.SOURCE_CAPITAL,
            role=VoiceGrant.ROLE_CAPITAL,
        )
        token = issue_voice_jwt(self.identity(guest))
        (access,) = self.call("get", "/status", token).json()["fleets"]
        self.assertEqual(access["fleet_title"], "")
        self.assertIsNone(access["fc_name"])
        self.assertIsNone(access["start_time"])

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

    def test_a_new_main_takes_over_the_old_mains_certificate(self):
        user = self.character.user
        old = VoiceCertificate.objects.create(
            identity=self.identity_, cert_hash="same-client"
        )
        new_main = self.alt(user, "new main")
        set_primary_character(user, new_main)
        new_identity = self.identity(new_main)
        token = connect.mint_token(new_identity)
        self.assertEqual(self.redeem(token, "same-client").status_code, 200)
        self.assertFalse(VoiceCertificate.objects.filter(pk=old.pk).exists())
        self.assertEqual(
            VoiceCertificate.objects.get(cert_hash="same-client").identity,
            new_identity,
        )

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
        with patch(
            "voice.endpoints.post_fleet_wings.publish_fleet_wing_pilots"
        ) as task, self.captureOnCommitCallbacks(execute=True):
            ok = self.call(
                "post",
                path,
                make_token(self.fc_user),
                {"wing_channels": {"1": "Auxiliary A"}},
            )
        self.assertEqual(ok.status_code, 204)
        # The republish is queued for this fleet, not done in the request.
        task.apply_async.assert_called_once_with(args=(self.fleet_.id,))

    def test_wing_republish_covers_this_fleets_wing_pilots_only(self):
        other = self.fleet(self.fc_user)
        for character_id, fleet, wing_id in (
            (501, self.fleet_, 3),
            (502, self.fleet_, None),
            (503, other, 3),
        ):
            VoiceGrant.objects.create(
                character_id=character_id,
                fleet=fleet,
                source=VoiceGrant.SOURCE_IN_FLEET,
                wing_id=wing_id,
            )
        with patch("voice.tasks.publisher.publish_characters") as publish:
            publish_fleet_wing_pilots(self.fleet_.id)
        self.assertEqual(list(publish.call_args.args[0]), [501])

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
