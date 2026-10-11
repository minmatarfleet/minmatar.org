from django.contrib.auth.models import User
from django.test import TestCase

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
