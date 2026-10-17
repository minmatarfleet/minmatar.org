import factory
from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase
from django.utils import timezone

from fleets.models import EveFleet

from surveys.constants import ACTIVITY_INACTIVE, COHORT_NEW
from surveys.helpers.autofill import build_member_context, build_segmentation


class AutofillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="pilot")

    def test_context_degrades_gracefully_for_bare_user(self):
        # A user with no EvePlayer/characters must still yield a full block.
        ctx = build_member_context(self.user)
        self.assertEqual(ctx["character_name"], "")
        self.assertEqual(ctx["tribe_names"], [])
        self.assertEqual(ctx["fleets_attended_quarter"], 0)
        self.assertEqual(ctx["activity_tier"], ACTIVITY_INACTIVE)
        self.assertEqual(ctx["tenure_cohort"], COHORT_NEW)

    def test_segmentation_is_subset_of_context(self):
        ctx = build_member_context(self.user)
        seg = build_segmentation(self.user, ctx)
        for key in (
            "corporation_name",
            "tenure_cohort",
            "activity_tier",
            "prime_time",
            "role_flags",
        ):
            self.assertIn(key, seg)

    def test_only_a_led_fleet_makes_an_fc(self):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="strategic",
                status="cancelled",
                start_time=timezone.now(),
                created_by=self.user,
            )
            self.assertNotIn(
                "fc", build_member_context(self.user)["role_flags"]
            )
            fleet.status = "complete"
            fleet.save()
        self.assertIn("fc", build_member_context(self.user)["role_flags"])
