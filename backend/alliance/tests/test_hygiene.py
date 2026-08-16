"""Unit tests for alliance hygiene classification (pure functions)."""

from app.test import TestCase

from alliance.helpers.hygiene import (
    MIN_APPROVE_DAYS,
    build_hygiene_payload,
    classify_leave,
    classify_trial,
    gang_bucket,
    slice_30d,
)


class GangBucketTestCase(TestCase):
    def test_buckets(self):
        self.assertEqual(gang_bucket(1), "small")
        self.assertEqual(gang_bucket(10), "small")
        self.assertEqual(gang_bucket(11), "medium")
        self.assertEqual(gang_bucket(25), "large")
        self.assertEqual(gang_bucket(40), "blob")


class Slice30dTestCase(TestCase):
    def test_quiet(self):
        self.assertEqual(slice_30d(0, 0, 0.0), "quiet")
        self.assertEqual(slice_30d(0, 0, 0.5), "quiet")

    def test_parts(self):
        self.assertEqual(slice_30d(2, 5, 1.2), "2F/5K/1.2h")
        self.assertEqual(slice_30d(1, 0, 0.0), "1F")


class ClassifyTrialTestCase(TestCase):
    def _base(self, **overrides):
        data = {
            "fleets": 5,
            "kills": 12,
            "kills_small": 9,
            "voice_hours": 6.0,
            "fleets_30d": 2,
            "kills_30d": 4,
            "voice_hours_30d": 2.0,
            "days_since_activity": 8,
            "alliance_days": 70,
            "linked_character_count": 2,
        }
        data.update(overrides)
        return data

    def test_approve_when_tenure_and_recency(self):
        result = classify_trial(**self._base())
        self.assertEqual(result["decision"], "approve")
        self.assertEqual(result["conf"], "high")
        self.assertIn("Mixed", result["path"])

    def test_too_early_under_60_days(self):
        result = classify_trial(**self._base(alliance_days=18))
        self.assertEqual(result["decision"], "too_early")
        self.assertIn("Too early", result["reason"])
        self.assertIn("18d", result["reason"])

    def test_too_early_unknown_tenure(self):
        result = classify_trial(**self._base(alliance_days=None))
        self.assertEqual(result["decision"], "too_early")

    def test_front_loaded_nudge(self):
        result = classify_trial(
            **self._base(
                fleets_30d=0,
                kills_30d=0,
                voice_hours_30d=0.0,
                days_since_activity=43,
            )
        )
        self.assertEqual(result["decision"], "nudge")
        self.assertIn("Front-loaded", result["reason"])

    def test_fail_dark_after_60_days(self):
        result = classify_trial(
            **self._base(
                fleets=0,
                kills=0,
                kills_small=0,
                voice_hours=0.0,
                fleets_30d=0,
                kills_30d=0,
                voice_hours_30d=0.0,
                days_since_activity=None,
                alliance_days=90,
            )
        )
        self.assertEqual(result["decision"], "fail")
        self.assertEqual(result["conf"], "high")

    def test_no_fail_before_60_days(self):
        result = classify_trial(
            **self._base(
                fleets=0,
                kills=0,
                kills_small=0,
                voice_hours=0.0,
                fleets_30d=0,
                kills_30d=0,
                voice_hours_30d=0.0,
                days_since_activity=None,
                alliance_days=20,
            )
        )
        self.assertEqual(result["decision"], "nudge")
        self.assertIn("New trial", result["reason"])

    def test_wrong_affiliation(self):
        result = classify_trial(
            **self._base(affiliation="Militia", requires_trial=False)
        )
        self.assertEqual(result["decision"], "wrong_affiliation")

    def test_small_gang_path(self):
        result = classify_trial(
            **self._base(
                fleets=0,
                kills=20,
                kills_small=14,
                voice_hours=1.0,
                fleets_30d=0,
                kills_30d=5,
            )
        )
        self.assertEqual(result["decision"], "approve")
        self.assertEqual(result["path"], "Small-gang")

    def test_min_approve_days_constant(self):
        self.assertEqual(MIN_APPROVE_DAYS, 60)


class ClassifyLeaveTestCase(TestCase):
    def test_away_zero_activity(self):
        result = classify_leave(fleets=0, kills=0, voice_hours=0.0)
        self.assertEqual(result["decision"], "recommend")
        self.assertEqual(result["story"], "Away")
        self.assertEqual(result["conf"], "high")

    def test_opsec_voice_without_fleets(self):
        result = classify_leave(fleets=0, kills=0, voice_hours=25.0)
        self.assertEqual(result["decision"], "recommend")
        self.assertEqual(result["story"], "OPSEC")

    def test_opsec_strong_kills_medium_conf(self):
        result = classify_leave(fleets=0, kills=40, voice_hours=2.0)
        self.assertEqual(result["decision"], "recommend")
        self.assertEqual(result["story"], "OPSEC")
        self.assertEqual(result["conf"], "medium")

    def test_exempt(self):
        result = classify_leave(
            fleets=0, kills=0, voice_hours=0.0, exempt="People Team"
        )
        self.assertEqual(result["decision"], "exempt")

    def test_restore_grace(self):
        result = classify_leave(
            fleets=0,
            kills=0,
            voice_hours=0.0,
            restored_from_leave_at="2026-07-20",
        )
        self.assertEqual(result["decision"], "keep")
        self.assertEqual(result["story"], "Restore grace")

    def test_rejoin_grace(self):
        result = classify_leave(
            fleets=1, kills=0, voice_hours=0.0, rejoin_grace=True
        )
        self.assertEqual(result["decision"], "keep")
        self.assertEqual(result["story"], "Rejoin grace")

    def test_keep_soft_line_with_support(self):
        result = classify_leave(fleets=3, kills=8, voice_hours=2.0)
        self.assertEqual(result["decision"], "keep")

    def test_recommend_soft_line_no_support(self):
        result = classify_leave(fleets=3, kills=0, voice_hours=0.0)
        self.assertEqual(result["decision"], "recommend")
        self.assertEqual(result["conf"], "medium")


class BuildHygienePayloadTestCase(TestCase):
    def test_groups_and_counts(self):
        trials = [
            {
                "decision": "approve",
                "conf": "high",
                "username": "a",
                "reason": "ok",
            },
            {
                "decision": "too_early",
                "conf": "high",
                "username": "b",
                "reason": "early",
            },
            {
                "decision": "fail",
                "conf": "high",
                "username": "c",
                "reason": "dark",
            },
            {
                "decision": "nudge",
                "conf": "medium",
                "username": "d",
                "reason": "fade",
            },
            {
                "decision": "hold",
                "conf": "medium",
                "username": "e",
                "reason": "hold",
            },
        ]
        leaves = [
            {
                "decision": "recommend",
                "conf": "high",
                "username": "x",
                "reason": "away",
            },
            {
                "decision": "keep",
                "conf": "—",
                "username": "y",
                "reason": "keep",
            },
            {
                "decision": "exempt",
                "conf": "—",
                "username": "z",
                "reason": "exempt",
            },
        ]
        payload = build_hygiene_payload(trials, leaves)
        self.assertEqual(payload["trial"]["counts"]["approve"], 1)
        self.assertEqual(payload["trial"]["counts"]["too_early"], 1)
        self.assertEqual(payload["trial"]["counts"]["fail"], 1)
        self.assertEqual(payload["trial"]["counts"]["nudge"], 1)
        self.assertEqual(payload["trial"]["counts"]["hold"], 1)
        self.assertNotIn("hold", payload["trial"]["buckets"])
        self.assertEqual(payload["leave"]["counts"]["recommended"], 1)
        self.assertEqual(payload["leave"]["counts"]["kept"], 1)
        self.assertEqual(payload["leave"]["counts"]["exempt"], 1)
        self.assertEqual(len(payload["leave"]["recommended"]), 1)
