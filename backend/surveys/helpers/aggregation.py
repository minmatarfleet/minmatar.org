"""Compute per-question, per-segment aggregates for a campaign."""

import logging
from collections import defaultdict

from surveys.constants import SEGMENT_ALL
from surveys.definitions.effective import build_effective_definition
from surveys.models import (
    SurveyAnswer,
    SurveyQuestionAggregate,
    SurveyResponse,
)

logger = logging.getLogger(__name__)


def _segment_keys(response: SurveyResponse) -> list[str]:
    keys = [SEGMENT_ALL]
    if response.corporation_name:
        keys.append(f"corp:{response.corporation_name}")
    if response.tenure_cohort:
        keys.append(f"cohort:{response.tenure_cohort}")
    if response.activity_tier:
        keys.append(f"tier:{response.activity_tier}")
    if response.prime_time:
        keys.append(f"tz:{response.prime_time}")
    return keys


def _accumulate_answer(q, ans, response, counts, numeric, dist):
    """Fold one answer into the running counts/numeric/distribution maps for
    every segment the response belongs to."""
    for seg in _segment_keys(response):
        counts[(ans.question_key, seg)] += 1
        if q.is_numeric() and ans.numeric_value is not None:
            numeric[(ans.question_key, seg)][0] += ans.numeric_value
            numeric[(ans.question_key, seg)][1] += 1
            bucket = str(int(ans.numeric_value))
            dist[(ans.question_key, seg)][bucket] += 1
        elif q.is_matrix() and isinstance(ans.json_value, dict):
            # nested {row: {option: count}}
            for row_key, option in ans.json_value.items():
                dist[(ans.question_key, seg)][f"{row_key}|{option}"] += 1
        elif q.allows_multiple() and isinstance(ans.json_value, list):
            for choice in ans.json_value:
                dist[(ans.question_key, seg)][str(choice)] += 1
        elif ans.choice_value:
            dist[(ans.question_key, seg)][ans.choice_value] += 1


def compute_aggregates(campaign) -> int:
    """Recompute SurveyQuestionAggregate rows for the campaign. Returns the
    number of aggregate rows written."""
    definition = build_effective_definition(campaign)
    if not definition:
        logger.warning("no definition for campaign %s", campaign.pk)
        return 0
    qmap = definition.question_map()

    responses = {r.pk: r for r in campaign.responses.all()}
    if not responses:
        campaign.aggregates.all().delete()
        return 0

    answers = SurveyAnswer.objects.filter(response__campaign=campaign)

    # (question_key, segment_key) -> distribution accumulator
    dist = defaultdict(lambda: defaultdict(float))
    # (question_key, segment_key) -> [sum, count] for numeric means
    numeric = defaultdict(lambda: [0.0, 0])
    counts = defaultdict(int)

    for ans in answers.iterator():
        q = qmap.get(ans.question_key)
        if not q:
            continue
        response = responses.get(ans.response_id)
        if not response:
            continue
        _accumulate_answer(q, ans, response, counts, numeric, dist)

    campaign.aggregates.all().delete()
    rows = []
    for (question_key, seg), n in counts.items():
        num = numeric.get((question_key, seg))
        mean = (num[0] / num[1]) if num and num[1] else None
        rows.append(
            SurveyQuestionAggregate(
                campaign=campaign,
                question_key=question_key,
                segment_key=seg,
                n=n,
                mean=mean,
                distribution=dict(dist[(question_key, seg)]),
            )
        )
    SurveyQuestionAggregate.objects.bulk_create(rows)
    return len(rows)
