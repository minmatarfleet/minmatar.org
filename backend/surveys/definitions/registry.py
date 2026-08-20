"""The code-defined community survey.

There is ONE canonical survey, used for every campaign regardless of quarter —
the question set is deliberately NOT varied by quarter, so results stay
comparable over time. Audience-gated blocks (e.g. onboarding for trials) and
per-campaign spotlight questions cover anything that needs to differ.
"""

from surveys.definitions.core import CORE_BLOCK
from surveys.definitions.modules import (
    CONTENT_BLOCK,
    CORP_BLOCK,
    ONBOARDING_BLOCK,
    OPEN_BLOCK,
    OPS_BLOCK,
)
from surveys.definitions.types import SurveyDefinition

COMMUNITY_SURVEY = SurveyDefinition(
    key="community",
    title="Community Survey",
    blocks=(
        CORE_BLOCK,
        ONBOARDING_BLOCK,  # audience="trial": shown only to trial members
        CONTENT_BLOCK,
        CORP_BLOCK,
        OPS_BLOCK,
        OPEN_BLOCK,
    ),
)

SURVEY_DEFINITIONS: dict[str, SurveyDefinition] = {
    COMMUNITY_SURVEY.key: COMMUNITY_SURVEY,
}


def get_definition(key: str) -> SurveyDefinition:
    """Resolve a campaign's definition. Falls back to the canonical survey so
    older campaigns (whose key predates the single-survey model) still render.
    """
    return SURVEY_DEFINITIONS.get(key) or COMMUNITY_SURVEY


def default_definition() -> SurveyDefinition:
    return COMMUNITY_SURVEY


def definition_keys() -> list[str]:
    return list(SURVEY_DEFINITIONS.keys())
