"""Tests for alliance health compute + endpoints."""

from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals
from django.utils import timezone
from app.test import TestCase
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncFeatures,
)
from groups.models import UserCommunityStatus

from alliance.helpers.health import compute_alliance_health, save_snapshot
from alliance.models import AllianceHealthSnapshot
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
)


class AllianceHealthComputeTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )
        Group.objects.get_or_create(name="Trial")
        Group.objects.get_or_create(name="On Leave")
        self.now = timezone.now()
        self.alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Minmatar Fleet Alliance",
            ticker="MFA",
        )
        self.corp = EveCorporation.objects.create(
            corporation_id=1000001,
            name="Test Corp",
            ticker="TEST",
            alliance=self.alliance,
            member_count=2,
        )
        self.user = User.objects.create_user(username="pilot_one")
        self.user2 = User.objects.create_user(username="pilot_two")
        self.char = EveCharacter.objects.create(
            character_id=900001,
            character_name="Pilot One",
            corporation_id=1000001,
            user=self.user,
        )
        self.char2 = EveCharacter.objects.create(
            character_id=900002,
            character_name="Pilot Two",
            corporation_id=1000001,
            user=self.user2,
        )
        EvePlayer.objects.create(
            nickname="pilot_one",
            user=self.user,
            primary_character=self.char,
        )
        EvePlayer.objects.create(
            nickname="pilot_two",
            user=self.user2,
            primary_character=self.char2,
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        UserCommunityStatus.objects.create(
            user=self.user2, status=UserCommunityStatus.STATUS_TRIAL
        )

        audience = EveFleetAudience.objects.create(name="Alliance Health Test")
        fleet = EveFleet.objects.create(
            description="test",
            type="strategic",
            start_time=self.now - timedelta(days=2),
            audience=audience,
        )
        instance = EveFleetInstance.objects.create(
            id=91001,
            eve_fleet=fleet,
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=900001,
            character_name="Pilot One",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=1,
            ship_name="Ship",
            solar_system_id=1,
            solar_system_name="System",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=self.now - timedelta(days=2)
        )

    def test_map_counts_fleet_attendee(self):
        payload = compute_alliance_health(now=self.now)
        self.assertEqual(payload["map_30d"], 1)
        self.assertEqual(payload["map_7d"], 1)
        self.assertEqual(payload["signals_30d"]["fleets"], 1)
        self.assertEqual(payload["roster_people"], 2)
        self.assertEqual(payload["status"]["active"], 1)
        self.assertEqual(payload["status"]["trial"], 1)

    def test_quiet_dark_when_no_activity(self):
        payload = compute_alliance_health(now=self.now)
        dark = payload["attention"]["dark"]
        dark_ids = {p["user_id"] for p in dark}
        self.assertIn(self.user2.id, dark_ids)
        self.assertNotIn(self.user.id, dark_ids)
        quiet = next(p for p in dark if p["user_id"] == self.user2.id)
        self.assertEqual(quiet["character_id"], 900002)
        self.assertEqual(quiet["corporation_id"], 1000001)

    def test_save_snapshot(self):
        snap = save_snapshot(compute_alliance_health(now=self.now))
        self.assertEqual(AllianceHealthSnapshot.objects.count(), 1)
        self.assertEqual(snap.payload["goal_map"], 500)


class AllianceHealthEndpointTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        clear_feature_cache()
        SyncFeatures().handle()
        clear_feature_cache()
        self.staff = User.objects.create_user(username="staff_viewer")
        perm = Permission.objects.get(
            codename="view_alliancehealth",
            content_type__app_label="alliance",
        )
        self.staff.user_permissions.add(perm)
        self.staff_token = jwt.encode(
            {"user_id": self.staff.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        AllianceHealthSnapshot.objects.create(
            computed_at=timezone.now(),
            payload={
                "computed_at": timezone.now().isoformat(),
                "goal_map": 500,
                "map_7d": 10,
                "map_14d": 20,
                "map_30d": 30,
                "roster_people": 40,
                "status": {"active": 1, "trial": 2, "on_leave": 3},
                "signals_30d": {
                    "fleets": 1,
                    "small_gang": 2,
                    "solo": 3,
                    "supply": 4,
                },
                "quiet": {"fading": 5, "dark": 6, "seasonal": 7},
                "monthly": [],
                "attention": {
                    "fading": [],
                    "dark": [
                        {
                            "user_id": 1,
                            "pilot": "Quiet Pilot",
                            "corp": "Test Corp",
                            "status": "trial",
                            "days_quiet": 100,
                            "active_months": 0,
                        }
                    ],
                    "seasonal": [],
                },
                "corporations": [
                    {
                        "corporation_id": 1,
                        "name": "Test Corp",
                        "characters": 10,
                        "humans": 5,
                        "active_90d": 3,
                        "active_90d_pct": 60.0,
                        "growth_90d_pct": 10.0,
                    }
                ],
                "cohorts": [
                    {
                        "month": "2026-07",
                        "label": "Jul",
                        "applications": 10,
                        "accepts": 8,
                        "academy_accepts": 2,
                        "fleet_first_week_pct": 50.0,
                        "fleet_1_30d_pct": 75.0,
                        "fleet_3_30d_pct": 25.0,
                    }
                ],
            },
        )

    def tearDown(self):
        clear_feature_cache()

    def _auth(self, token: str):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_overview_403_without_permission(self):
        stranger = User.objects.create_user(username="nope")
        token = jwt.encode(
            {"user_id": stranger.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 403)

    def test_overview_200_with_permission(self):
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["map_30d"], 30)
        self.assertEqual(body["goal_map"], 500)

    def test_attention_dark(self):
        response = self.client.get(
            "/api/alliance/health/attention?bucket=dark",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["bucket"], "dark")
        self.assertEqual(len(body["pilots"]), 1)
        self.assertEqual(body["pilots"][0]["pilot"], "Quiet Pilot")

    def test_corporations_and_cohorts(self):
        corps = self.client.get(
            "/api/alliance/health/corporations",
            **self._auth(self.staff_token),
        )
        self.assertEqual(corps.status_code, 200)
        self.assertEqual(len(corps.json()["corporations"]), 1)
        cohorts = self.client.get(
            "/api/alliance/health/cohorts",
            **self._auth(self.staff_token),
        )
        self.assertEqual(cohorts.status_code, 200)
        self.assertEqual(cohorts.json()["cohorts"][0]["accepts"], 8)

    def test_503_without_snapshot(self):
        AllianceHealthSnapshot.objects.all().delete()
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 503)
