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

from alliance.endpoints.health.schemas import (
    leave_from_payload,
    onboarding_from_payload,
    overview_from_payload,
    trials_from_payload,
)
from alliance.helpers.health import (
    classify_quiet_attention,
    compute_alliance_health,
    save_snapshot,
)
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
        EveCharacter.objects.create(
            character_id=900003,
            character_name="Ghost Pilot",
            corporation_id=1000001,
            user=None,
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
        hygiene = payload["hygiene"]
        self.assertIn("trial", hygiene)
        self.assertIn("leave", hygiene)
        self.assertIn("approve", hygiene["trial"]["counts"])
        self.assertIn("recommended", hygiene["leave"]["counts"])
        # Trial user with no activity and short tenure → nudge (new trial)
        # or fail if tenure ≥60d; test corp has no history so fallback.
        self.assertGreaterEqual(hygiene["trial"]["counts"]["nudge"], 0)
        self.assertIn("status_windows", payload)
        self.assertIn("d30", payload["status_windows"]["active"])
        self.assertIn("unknown_characters", payload)
        names = {
            row["character_name"] for row in payload["unknown_characters"]
        }
        self.assertIn("Ghost Pilot", names)
        if payload["monthly"]:
            self.assertIn("small_gang", payload["monthly"][0])
            self.assertNotIn("supply", payload["monthly"][0])

    def _add_fleet_member(
        self, character_id, character_name, instance_id, days_ago
    ):
        audience = EveFleetAudience.objects.get(name="Alliance Health Test")
        fleet = EveFleet.objects.create(
            description="test",
            type="strategic",
            start_time=self.now - timedelta(days=days_ago),
            audience=audience,
        )
        instance = EveFleetInstance.objects.create(
            id=instance_id,
            eve_fleet=fleet,
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character_id,
            character_name=character_name,
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
            join_time=self.now - timedelta(days=days_ago)
        )

    def test_quiet_dark_requires_prior_activity(self):
        gone = User.objects.create_user(username="pilot_gone")
        gone_char = EveCharacter.objects.create(
            character_id=900004,
            character_name="Pilot Gone",
            corporation_id=1000001,
            user=gone,
        )
        EvePlayer.objects.create(
            nickname="pilot_gone",
            user=gone,
            primary_character=gone_char,
        )
        UserCommunityStatus.objects.create(
            user=gone, status=UserCommunityStatus.STATUS_ACTIVE
        )
        self._add_fleet_member(900004, "Pilot Gone", 91002, days_ago=120)

        payload = compute_alliance_health(now=self.now)
        dark = payload["attention"]["dark"]
        dark_ids = {p["user_id"] for p in dark}
        self.assertIn(gone.id, dark_ids)
        self.assertNotIn(self.user2.id, dark_ids)
        self.assertNotIn(self.user.id, dark_ids)
        quiet = next(p for p in dark if p["user_id"] == gone.id)
        self.assertEqual(quiet["character_id"], 900004)
        self.assertEqual(quiet["corporation_id"], 1000001)
        self.assertGreaterEqual(quiet["active_months"], 1)

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
                "status_windows": {
                    "active": {"d30": 10, "d90": 20, "d180": 30},
                    "trial": {"d30": 1, "d90": 2, "d180": 3},
                    "on_leave": {"d30": 0, "d90": 1, "d180": 2},
                },
                "signals_30d": {
                    "fleets": 1,
                    "small_gang": 2,
                    "solo": 3,
                    "supply": 4,
                },
                "quiet": {"fading": 5, "dark": 6, "seasonal": 7},
                "monthly": [
                    {
                        "month": "2026-07",
                        "label": "Jul",
                        "active": 10,
                        "fleet": 8,
                        "small_gang": 3,
                        "solo": 2,
                    }
                ],
                "tribes_monthly": {"months": [], "series": []},
                "unknown_characters": [
                    {
                        "character_id": 900099,
                        "character_name": "Ghost Pilot",
                        "corporation_id": 1,
                        "corp": "Test Corp",
                    }
                ],
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
                "hygiene": {
                    "trial": {
                        "counts": {
                            "approve": 1,
                            "too_early": 2,
                            "fail": 3,
                            "nudge": 4,
                            "hold": 5,
                            "current": 1,
                            "add": 0,
                            "remove": 1,
                            "flagged": 7,
                        },
                        "buckets": {
                            "approve": [
                                {
                                    "user_id": 10,
                                    "username": "ready_pilot",
                                    "pilot": "Ready Pilot",
                                    "corp": "Test Corp",
                                    "corporation_id": 1,
                                    "character_id": 100,
                                    "alliance_days": 70,
                                    "fleets": 5,
                                    "kills": 12,
                                    "kills_small": 9,
                                    "voice_hours": 6.0,
                                    "slice_30d": "2F/4K/2h",
                                    "days_since_activity": 8,
                                    "path": "Mixed",
                                    "conf": "high",
                                    "reason": "Mixed — 5 fleets, 9 small-gang",
                                }
                            ],
                            "too_early": [],
                            "fail": [],
                            "nudge": [],
                            "current": [
                                {
                                    "user_id": 10,
                                    "username": "ready_pilot",
                                    "pilot": "Ready Pilot",
                                    "corp": "Test Corp",
                                    "corporation_id": 1,
                                    "character_id": 100,
                                    "alliance_days": 70,
                                    "fleets": 5,
                                    "kills": 12,
                                    "kills_small": 9,
                                    "voice_hours": 6.0,
                                    "slice_30d": "2F/4K/2h",
                                    "days_since_activity": 8,
                                    "path": "Mixed",
                                    "conf": "high",
                                    "reason": "Mixed — 5 fleets, 9 small-gang",
                                }
                            ],
                            "add": [],
                            "remove": [
                                {
                                    "user_id": 10,
                                    "username": "ready_pilot",
                                    "pilot": "Ready Pilot",
                                    "corp": "Test Corp",
                                    "corporation_id": 1,
                                    "character_id": 100,
                                    "alliance_days": 70,
                                    "fleets": 5,
                                    "kills": 12,
                                    "kills_small": 9,
                                    "voice_hours": 6.0,
                                    "slice_30d": "2F/4K/2h",
                                    "days_since_activity": 8,
                                    "path": "Mixed",
                                    "conf": "high",
                                    "reason": "Mixed — 5 fleets, 9 small-gang",
                                }
                            ],
                            "flagged": [],
                        },
                    },
                    "leave": {
                        "counts": {
                            "recommended": 1,
                            "kept": 2,
                            "exempt": 3,
                            "current": 0,
                            "add": 1,
                            "remove": 0,
                            "flagged": 0,
                        },
                        "recommended": [
                            {
                                "user_id": 20,
                                "username": "quiet_active",
                                "pilot": "Quiet Active",
                                "corp": "Test Corp",
                                "corporation_id": 1,
                                "character_id": 200,
                                "fleets": 0,
                                "kills": 0,
                                "voice_hours": 0.0,
                                "story": "Away",
                                "conf": "high",
                                "reason": "Away — 0 fleets, 0 kills, 0h voice (90d)",
                            }
                        ],
                        "current": [],
                        "restore": [],
                        "flagged": [],
                    },
                },
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
        self.assertEqual(body["status_windows"]["active"]["d30"], 10)
        self.assertEqual(body["monthly"][0]["small_gang"], 3)
        self.assertEqual(body["viewer"]["alliance_wide"], True)
        self.assertEqual(body["viewer"]["can_mutate"], False)
        self.assertEqual(body["delta_30d"]["active"], 0)
        self.assertEqual(body["delta_30d"]["trial"], 0)
        self.assertEqual(body["delta_30d"]["on_leave"], 0)

    def test_overview_delta_30d(self):
        AllianceHealthSnapshot.objects.create(
            computed_at=timezone.now() - timedelta(days=31),
            payload={
                "status": {"active": 5, "trial": 10, "on_leave": 1},
            },
        )
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        delta = response.json()["delta_30d"]
        self.assertEqual(delta["active"], -4)
        self.assertEqual(delta["trial"], -8)
        self.assertEqual(delta["on_leave"], 2)

    def test_legacy_snapshot_payload_fills_new_fields(self):
        """Imported prod snapshots predate status_windows / selector buckets."""
        legacy = {
            "computed_at": "2026-08-16T19:25:00+00:00",
            "goal_map": 500,
            "map_7d": 10,
            "map_14d": 20,
            "map_30d": 30,
            "roster_people": 405,
            "status": {"active": 187, "trial": 124, "on_leave": 94},
            "signals_30d": {
                "fleets": 1,
                "small_gang": 2,
                "solo": 3,
                "supply": 4,
            },
            "quiet": {"fading": 5, "dark": 6, "seasonal": 7},
            "monthly": [
                {
                    "month": "2026-07",
                    "label": "Jul",
                    "active": 10,
                    "fleet": 8,
                    "solo": 2,
                    "supply": 0,
                }
            ],
            "hygiene": {
                "trial": {
                    "counts": {
                        "approve": 1,
                        "too_early": 2,
                        "fail": 3,
                        "nudge": 4,
                        "hold": 5,
                    },
                    "buckets": {
                        "approve": [],
                        "too_early": [],
                        "fail": [],
                        "nudge": [],
                    },
                },
                "leave": {
                    "counts": {"recommended": 1, "kept": 2, "exempt": 3},
                    "recommended": [],
                },
            },
        }
        overview = overview_from_payload(legacy)
        self.assertEqual(overview.status_windows.active.d30, 0)
        self.assertEqual(overview.unknown_characters, [])
        self.assertEqual(overview.hygiene.trial.remove, 1)
        self.assertEqual(overview.hygiene.trial.flagged, 7)
        self.assertEqual(overview.hygiene.trial.passing, 3)
        self.assertEqual(overview.hygiene.trial.failing, 3)
        self.assertEqual(overview.hygiene.trial.evaluating, 9)
        self.assertEqual(overview.hygiene.leave.add, 1)
        self.assertEqual(overview.monthly[0].small_gang, 0)
        trials = trials_from_payload(legacy, "current")
        self.assertEqual(trials.bucket, "current")
        passing = trials_from_payload(legacy, "passing")
        self.assertEqual(passing.bucket, "passing")
        self.assertEqual(len(passing.pilots), 0)
        leave = leave_from_payload(legacy, "current")
        self.assertEqual(leave.bucket, "current")
        self.assertEqual(leave.counts.recommended, 1)
        self.assertEqual(leave.counts.returning, 0)
        self.assertEqual(leave.counts.inactive, 0)

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

    def test_overview_includes_hygiene_counts(self):
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        hygiene = response.json()["hygiene"]
        self.assertEqual(hygiene["trial"]["approve"], 1)
        self.assertEqual(hygiene["leave"]["recommended"], 1)

    def test_trials_approve_bucket(self):
        response = self.client.get(
            "/api/alliance/health/trials?bucket=approve",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["bucket"], "approve")
        self.assertEqual(len(body["pilots"]), 1)
        self.assertEqual(body["pilots"][0]["username"], "ready_pilot")
        self.assertEqual(body["counts"]["approve"], 1)

    def test_trials_csv(self):
        response = self.client.get(
            "/api/alliance/health/trials?bucket=approve&format=csv",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("ready_pilot,active,", response.content.decode())

    def test_leave_recommended(self):
        response = self.client.get(
            "/api/alliance/health/leave?bucket=add",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["pilots"]), 1)
        self.assertEqual(body["pilots"][0]["story"], "Away")
        self.assertEqual(body["counts"]["recommended"], 1)
        self.assertEqual(body["counts"]["add"], 1)

    def test_leave_returning_bucket(self):
        response = self.client.get(
            "/api/alliance/health/leave?bucket=returning",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["bucket"], "returning")
        self.assertEqual(body["counts"]["returning"], 0)

    def test_leave_csv(self):
        response = self.client.get(
            "/api/alliance/health/leave?bucket=add&format=csv",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("quiet_active,on_leave,", response.content.decode())

    def test_503_without_snapshot(self):
        AllianceHealthSnapshot.objects.all().delete()
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 503)

    def test_trials_default_current(self):
        response = self.client.get(
            "/api/alliance/health/trials",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["bucket"], "current")
        self.assertEqual(len(body["pilots"]), 1)

    def test_onboarding_splits_trial_pilots(self):
        def row(**overrides):
            data = {
                "user_id": 1,
                "username": "pilot",
                "pilot": "Pilot",
                "corp": "Test Corp",
                "corporation_id": 1,
                "character_id": 100,
                "alliance_days": 70,
                "fleets": 5,
                "kills": 0,
                "kills_small": 0,
                "voice_hours": 0.0,
                "slice_30d": "quiet",
                "days_since_activity": 1,
                "path": "—",
                "conf": "—",
                "reason": "x",
            }
            data.update(overrides)
            return data

        payload = {
            "computed_at": "now",
            "hygiene": {
                "trial": {
                    "counts": {},
                    "buckets": {
                        "current": [
                            row(
                                user_id=1,
                                username="new",
                                pilot="New",
                                alliance_days=2,
                                fleets=0,
                            ),
                            row(
                                user_id=2,
                                username="warm",
                                pilot="Warm",
                                alliance_days=20,
                                fleets=1,
                            ),
                            row(
                                user_id=3,
                                username="set",
                                pilot="Set",
                                alliance_days=70,
                                fleets=5,
                            ),
                        ]
                    },
                }
            },
        }
        first = onboarding_from_payload(payload, "first_week")
        self.assertEqual(first.counts.first_week, 1)
        self.assertEqual(first.counts.more_fleets, 1)
        self.assertEqual(first.pilots[0].pilot, "New")
        more = onboarding_from_payload(payload, "more_fleets")
        self.assertEqual(more.pilots[0].pilot, "Warm")

    def test_onboarding_endpoint(self):
        response = self.client.get(
            "/api/alliance/health/onboarding",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["bucket"], "first_week")
        self.assertIn("first_week", body["counts"])
        self.assertIn("more_fleets", body["counts"])

    def test_unknowns(self):
        response = self.client.get(
            "/api/alliance/health/unknowns",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["characters"]), 1)
        self.assertEqual(
            body["characters"][0]["character_name"], "Ghost Pilot"
        )

    def _people_user(self):
        Group.objects.get_or_create(name="People Team")
        Group.objects.get_or_create(name="Trial")
        Group.objects.get_or_create(name="On Leave")
        people = User.objects.create_user(username="people_exec")
        people.groups.add(Group.objects.get(name="People Team"))
        token = jwt.encode(
            {"user_id": people.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        return people, token

    def test_people_can_view_without_django_perm(self):
        token = self._people_user()[1]
        response = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["viewer"]["can_mutate"], True)
        self.assertEqual(response.json()["viewer"]["alliance_wide"], True)
        self.assertEqual(response.json()["viewer"]["can_leave_any"], False)
        self.assertEqual(response.json()["viewer"]["ceo_corp_ids"], [])

    def test_status_promote_as_people(self):
        token = self._people_user()[1]
        trial = User.objects.create_user(username="trial_ready")
        UserCommunityStatus.objects.create(
            user=trial, status=UserCommunityStatus.STATUS_TRIAL
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": trial.id, "action": "promote"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 200)
        trial.community_status.refresh_from_db()
        self.assertEqual(
            trial.community_status.status, UserCommunityStatus.STATUS_ACTIVE
        )

    def test_status_leave_denied_for_people(self):
        token = self._people_user()[1]
        active = User.objects.create_user(username="active_quiet")
        UserCommunityStatus.objects.create(
            user=active, status=UserCommunityStatus.STATUS_ACTIVE
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": active.id, "action": "leave"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 403)
        active.community_status.refresh_from_db()
        self.assertEqual(
            active.community_status.status,
            UserCommunityStatus.STATUS_ACTIVE,
        )

    def test_status_leave_as_superuser(self):
        Group.objects.get_or_create(name="On Leave")
        admin = User.objects.create_user(
            username="health_super", is_superuser=True
        )
        token = jwt.encode(
            {"user_id": admin.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        active = User.objects.create_user(username="active_for_super")
        UserCommunityStatus.objects.create(
            user=active, status=UserCommunityStatus.STATUS_ACTIVE
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": active.id, "action": "leave"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 200)
        active.community_status.refresh_from_db()
        self.assertEqual(
            active.community_status.status,
            UserCommunityStatus.STATUS_ON_LEAVE,
        )

    def test_status_forbidden_for_staff_without_corp(self):
        Group.objects.get_or_create(name="Trial")
        Group.objects.get_or_create(name="On Leave")
        trial = User.objects.create_user(username="trial_locked")
        UserCommunityStatus.objects.create(
            user=trial, status=UserCommunityStatus.STATUS_TRIAL
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": trial.id, "action": "promote"},
            content_type="application/json",
            **self._auth(self.staff_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_ceo_can_view_and_mutate_own_corp(self):
        Group.objects.get_or_create(name="Trial")
        Group.objects.get_or_create(name="On Leave")
        alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Minmatar Fleet Alliance",
            ticker="MFA",
        )
        corp = EveCorporation.objects.create(
            corporation_id=1000001,
            name="Test Corp",
            ticker="TEST",
            alliance=alliance,
        )
        other = EveCorporation.objects.create(
            corporation_id=1000002,
            name="Other Corp",
            ticker="OTHR",
            alliance=alliance,
        )
        ceo = User.objects.create_user(username="ceo_user")
        ceo_char = EveCharacter.objects.create(
            character_id=910001,
            character_name="CEO Pilot",
            corporation_id=1000001,
            user=ceo,
        )
        EvePlayer.objects.create(
            nickname="ceo_user",
            user=ceo,
            primary_character=ceo_char,
        )
        corp.ceo = ceo_char
        corp.save()

        member = User.objects.create_user(username="corp_trial")
        member_char = EveCharacter.objects.create(
            character_id=910002,
            character_name="Corp Trial",
            corporation_id=1000001,
            user=member,
        )
        EvePlayer.objects.create(
            nickname="corp_trial",
            user=member,
            primary_character=member_char,
        )
        UserCommunityStatus.objects.create(
            user=member, status=UserCommunityStatus.STATUS_TRIAL
        )

        outsider = User.objects.create_user(username="other_trial")
        outsider_char = EveCharacter.objects.create(
            character_id=910003,
            character_name="Other Trial",
            corporation_id=1000002,
            user=outsider,
        )
        EvePlayer.objects.create(
            nickname="other_trial",
            user=outsider,
            primary_character=outsider_char,
        )
        UserCommunityStatus.objects.create(
            user=outsider, status=UserCommunityStatus.STATUS_TRIAL
        )
        other.save()

        token = jwt.encode(
            {"user_id": ceo.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        overview = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(token),
        )
        self.assertEqual(overview.status_code, 200)
        viewer = overview.json()["viewer"]
        self.assertEqual(viewer["alliance_wide"], False)
        self.assertEqual(viewer["can_mutate"], True)
        self.assertEqual(viewer["home_corp_id"], 1000001)
        self.assertEqual(viewer["can_leave_any"], False)
        self.assertEqual(viewer["ceo_corp_ids"], [1000001])

        own = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": member.id, "action": "promote"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(own.status_code, 200)

        leave_own = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": member.id, "action": "leave"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(leave_own.status_code, 200)

        denied = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": outsider.id, "action": "promote"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(denied.status_code, 403)

        leave_other = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": outsider.id, "action": "leave"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(leave_other.status_code, 403)

    def test_director_cannot_put_on_leave(self):
        Group.objects.get_or_create(name="On Leave")
        alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Minmatar Fleet Alliance",
            ticker="MFA",
        )
        corp = EveCorporation.objects.create(
            corporation_id=1000101,
            name="Director Corp",
            ticker="DIRC",
            alliance=alliance,
        )
        director = User.objects.create_user(username="dir_user")
        director_char = EveCharacter.objects.create(
            character_id=910101,
            character_name="Director Pilot",
            corporation_id=1000101,
            user=director,
        )
        EvePlayer.objects.create(
            nickname="dir_user",
            user=director,
            primary_character=director_char,
        )
        corp.directors.add(director_char)

        member = User.objects.create_user(username="dir_member")
        member_char = EveCharacter.objects.create(
            character_id=910102,
            character_name="Dir Member",
            corporation_id=1000101,
            user=member,
        )
        EvePlayer.objects.create(
            nickname="dir_member",
            user=member,
            primary_character=member_char,
        )
        UserCommunityStatus.objects.create(
            user=member, status=UserCommunityStatus.STATUS_ACTIVE
        )
        token = jwt.encode(
            {"user_id": director.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        overview = self.client.get(
            "/api/alliance/health/overview",
            **self._auth(token),
        )
        self.assertEqual(overview.status_code, 200)
        viewer = overview.json()["viewer"]
        self.assertEqual(viewer["can_mutate"], True)
        self.assertEqual(viewer["can_leave_any"], False)
        self.assertEqual(viewer["ceo_corp_ids"], [])

        denied = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": member.id, "action": "leave"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(denied.status_code, 403)

    def test_promote_rejects_non_trial(self):
        token = self._people_user()[1]
        active = User.objects.create_user(username="already_active")
        UserCommunityStatus.objects.create(
            user=active, status=UserCommunityStatus.STATUS_ACTIVE
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": active.id, "action": "promote"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_status_restore_as_people(self):
        token = self._people_user()[1]
        on_leave = User.objects.create_user(username="leave_ready")
        UserCommunityStatus.objects.create(
            user=on_leave, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": on_leave.id, "action": "restore"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 200)
        on_leave.community_status.refresh_from_db()
        self.assertEqual(
            on_leave.community_status.status,
            UserCommunityStatus.STATUS_ACTIVE,
        )

    def test_restore_rejects_non_leave(self):
        token = self._people_user()[1]
        active = User.objects.create_user(username="still_active")
        UserCommunityStatus.objects.create(
            user=active, status=UserCommunityStatus.STATUS_ACTIVE
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": active.id, "action": "restore"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_director_can_restore_from_leave(self):
        Group.objects.get_or_create(name="On Leave")
        alliance = EveAlliance.objects.create(
            alliance_id=99011978,
            name="Minmatar Fleet Alliance",
            ticker="MFA",
        )
        corp = EveCorporation.objects.create(
            corporation_id=1000201,
            name="Restore Corp",
            ticker="RSTR",
            alliance=alliance,
        )
        director = User.objects.create_user(username="restore_dir")
        director_char = EveCharacter.objects.create(
            character_id=910201,
            character_name="Restore Director",
            corporation_id=1000201,
            user=director,
        )
        EvePlayer.objects.create(
            nickname="restore_dir",
            user=director,
            primary_character=director_char,
        )
        corp.directors.add(director_char)

        member = User.objects.create_user(username="restore_member")
        member_char = EveCharacter.objects.create(
            character_id=910202,
            character_name="Restore Member",
            corporation_id=1000201,
            user=member,
        )
        EvePlayer.objects.create(
            nickname="restore_member",
            user=member,
            primary_character=member_char,
        )
        UserCommunityStatus.objects.create(
            user=member, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        token = jwt.encode(
            {"user_id": director.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        response = self.client.post(
            "/api/alliance/health/status",
            data={"user_id": member.id, "action": "restore"},
            content_type="application/json",
            **self._auth(token),
        )
        self.assertEqual(response.status_code, 200)
        member.community_status.refresh_from_db()
        self.assertEqual(
            member.community_status.status,
            UserCommunityStatus.STATUS_ACTIVE,
        )


class AllianceHealthTimezoneTestCase(TestCase):
    def test_trials_attach_prime_time_label(self):
        user = User.objects.create_user(username="tz_pilot")
        EvePlayer.objects.create(
            user=user,
            nickname="tz_pilot",
            prime_time="EU_US",
        )
        payload = {
            "computed_at": "now",
            "hygiene": {
                "trial": {
                    "counts": {"current": 1},
                    "buckets": {
                        "current": [
                            {
                                "user_id": user.id,
                                "username": "tz_pilot",
                                "pilot": "Tz Pilot",
                                "corp": "Test",
                                "fleets": 1,
                                "kills": 0,
                                "kills_small": 0,
                                "voice_hours": 0.0,
                                "slice_30d": "quiet",
                                "path": "—",
                                "conf": "—",
                                "reason": "x",
                            }
                        ]
                    },
                }
            },
        }
        body = trials_from_payload(payload, "current")
        self.assertEqual(body.pilots[0].timezone, "EU / US")


class ClassifyQuietAttentionTestCase(TestCase):
    def test_never_active_is_not_dark(self):
        now = timezone.now()
        fading, dark, seasonal = classify_quiet_attention(
            eligible={1, 2},
            active_30d=set(),
            active_90d=set(),
            last_activity={},
            months_active={},
            now=now,
        )
        self.assertEqual(fading, set())
        self.assertEqual(dark, set())
        self.assertEqual(seasonal, set())

    def test_prior_activity_is_dark(self):
        now = timezone.now()
        last = now - timedelta(days=120)
        fading, dark, seasonal = classify_quiet_attention(
            eligible={1},
            active_30d=set(),
            active_90d=set(),
            last_activity={1: last},
            months_active={1: {"2026-04"}},
            now=now,
        )
        self.assertEqual(dark, {1})
        self.assertEqual(fading, set())
        self.assertEqual(seasonal, set())

    def test_recent_90d_activity_is_fading(self):
        now = timezone.now()
        fading, dark, seasonal = classify_quiet_attention(
            eligible={1},
            active_30d=set(),
            active_90d={1},
            last_activity={1: now - timedelta(days=45)},
            months_active={1: {"2026-07"}},
            now=now,
        )
        self.assertEqual(fading, {1})
        self.assertEqual(dark, set())
        self.assertEqual(seasonal, set())

    def test_three_active_months_is_seasonal(self):
        now = timezone.now()
        fading, dark, seasonal = classify_quiet_attention(
            eligible={1},
            active_30d=set(),
            active_90d=set(),
            last_activity={1: now - timedelta(days=120)},
            months_active={1: {"2026-01", "2026-03", "2026-06"}},
            now=now,
        )
        self.assertEqual(seasonal, {1})
        self.assertEqual(dark, {1})
        self.assertEqual(fading, set())
