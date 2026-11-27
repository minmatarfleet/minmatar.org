"""Exit and alliance move surveys (#3198, design 07).

Sent once to a pilot who left a tracked corporation on their own, and read
only by the Alliance Executor. Kept apart from ``SURVEY_DEFINITIONS`` so the
quarterly community campaigns never pick them up. The questions are the
issue's drafts; changing one means a new ``EXIT_DEFINITION_VERSION``.
"""

from surveys.constants import TYPE_MULTI, TYPE_SCALE5, TYPE_TEXT
from surveys.definitions.types import Block, Question, SurveyDefinition

EXIT_DEFINITION_VERSION = 1

ENJOY = ("Not at all", "A lot")
GOOD = ("Poor", "Great")

RATINGS = Block(
    key="exit.ratings",
    title="Your time in the corporation",
    questions=(
        Question(
            key="exit.enjoyment",
            type=TYPE_SCALE5,
            label="Overall, how much did you enjoy {corporation}?",
            required=True,
            scale_labels=ENJOY,
        ),
        Question(
            key="exit.leadership",
            type=TYPE_SCALE5,
            label="Leadership",
            required=True,
            scale_labels=GOOD,
        ),
        Question(
            key="exit.activity",
            type=TYPE_SCALE5,
            label="Activity and content",
            required=True,
            scale_labels=GOOD,
        ),
        Question(
            key="exit.welcome",
            type=TYPE_SCALE5,
            label="Feeling welcome and included",
            required=True,
            scale_labels=GOOD,
        ),
    ),
)

WHY_LEFT_CHOICES = (
    "I was inactive in EVE",
    "The corporation was inactive",
    "Leadership issues",
    "Timezone",
    "I wanted different content",
    "I joined friends elsewhere",
    "I'm quitting EVE",
    "Other",
)

PROBLEM = Question(
    key="exit.problem",
    type=TYPE_TEXT,
    label="Was there a problem with the corporation we should know about?",
)
ANYTHING_ELSE = Question(
    key="exit.anything_else",
    type=TYPE_TEXT,
    label="Anything else?",
)

EXIT_SURVEY = SurveyDefinition(
    key="exit",
    title="Exit survey",
    blocks=(
        RATINGS,
        Block(
            key="exit.leaving",
            title="Leaving",
            questions=(
                Question(
                    key="exit.why_left",
                    type=TYPE_MULTI,
                    label="Why did you leave?",
                    help="Pick any that fit",
                    choices=WHY_LEFT_CHOICES,
                ),
                PROBLEM,
                ANYTHING_ELSE,
            ),
        ),
    ),
)

ALLIANCE_MOVE_SURVEY = SurveyDefinition(
    key="alliance_move",
    title="Alliance move survey",
    blocks=(
        RATINGS,
        Block(
            key="move.moving",
            title="Moving",
            questions=(
                Question(
                    key="move.why",
                    type=TYPE_TEXT,
                    label="Why did you move to {new_corporation}?",
                ),
                Question(
                    key="move.onboarding",
                    type=TYPE_SCALE5,
                    label="What was {new_corporation}'s onboarding like?",
                    scale_labels=GOOD,
                ),
                PROBLEM,
                ANYTHING_ELSE,
            ),
        ),
    ),
)

EXIT_DEFINITIONS = {
    EXIT_SURVEY.key: EXIT_SURVEY,
    ALLIANCE_MOVE_SURVEY.key: ALLIANCE_MOVE_SURVEY,
}
