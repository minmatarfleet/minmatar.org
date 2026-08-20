from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from surveys.constants import STATUS_OPEN
from surveys.helpers.aggregation import compute_aggregates
from surveys.models import SurveyAnswer, SurveyCampaign, SurveyResponse


class AggregateTests(TestCase):
    def setUp(self):
        self.campaign = SurveyCampaign.objects.create(
            year=2027,
            quarter=1,
            definition_key="community",
            title="2027 Q1",
            status=STATUS_OPEN,
            opens_at=timezone.now(),
        )

    def _response(self, username, corp, cohort, sat):
        user = User.objects.create(username=username)
        resp = SurveyResponse.objects.create(
            campaign=self.campaign,
            user=user,
            corporation_name=corp,
            tenure_cohort=cohort,
            activity_tier="core",
        )
        SurveyAnswer.objects.create(
            response=resp, question_key="core.satisfaction", numeric_value=sat
        )
        return resp

    def test_segment_means(self):
        self._response("a", "A-RAT", "1yr+", 4)
        self._response("b", "A-RAT", "<30d", 2)
        self._response("c", "SLTAR", "1yr+", 5)
        compute_aggregates(self.campaign)

        all_agg = self.campaign.aggregates.get(
            question_key="core.satisfaction", segment_key="all"
        )
        self.assertEqual(all_agg.n, 3)
        self.assertAlmostEqual(all_agg.mean, (4 + 2 + 5) / 3)

        arat = self.campaign.aggregates.get(
            question_key="core.satisfaction", segment_key="corp:A-RAT"
        )
        self.assertEqual(arat.n, 2)
        self.assertAlmostEqual(arat.mean, 3.0)

        new_cohort = self.campaign.aggregates.get(
            question_key="core.satisfaction", segment_key="cohort:<30d"
        )
        self.assertEqual(new_cohort.n, 1)
        self.assertAlmostEqual(new_cohort.mean, 2.0)
