"""The Health Core — the never-changing, trendable heart of every survey.

The wording and keys of these questions MUST NOT change between quarters.
That stability is what keeps results comparable from one quarter to the next.
"""

from surveys.constants import (
    TYPE_AGREE,
    TYPE_SCALE5,
)
from surveys.definitions.types import Block, Question

CORE_BLOCK = Block(
    key="core",
    title="How it's going",
    description=(
        "A handful of questions we ask in exactly the same words every "
        "quarter, so we can watch the line move over time."
    ),
    questions=(
        Question(
            key="core.satisfaction",
            type=TYPE_SCALE5,
            label="Overall, how satisfied are you with Minmatar Fleet right now?",
            required=True,
            trendable=True,
            scale_labels=("Frustrated", "Thrilled"),
        ),
        Question(
            key="core.enps",
            type=TYPE_SCALE5,
            label=(
                "How likely are you to recommend Minmatar Fleet to a friend "
                "who plays EVE?"
            ),
            scale_labels=("Never", "Definitely"),
            required=True,
            trendable=True,
        ),
        Question(
            key="core.belonging",
            type=TYPE_AGREE,
            label="I feel like I belong here and have people I fly with.",
            required=True,
            trendable=True,
        ),
        Question(
            key="core.retention",
            type=TYPE_SCALE5,
            label="How likely are you to still be active in Minmatar Fleet in 3 months?",
            required=True,
            trendable=True,
            scale_labels=("Very unlikely", "Very likely"),
        ),
        Question(
            key="core.heard",
            type=TYPE_AGREE,
            label="Leadership listens to members and acts on their feedback.",
            required=True,
            trendable=True,
        ),
    ),
)
