"""Standing operational block, open floor, and rotating deep-dive modules."""

from surveys.constants import (
    TYPE_AGREE,
    TYPE_MATRIX,
    TYPE_SCALE5,
    TYPE_SINGLE,
    TYPE_TEXT,
)
from surveys.definitions.types import Block, Question

# Column option sets reused across matrix questions.
TEAM_RATING_OPTIONS = ("1", "2", "3", "4", "5", "N/A")

# ---------------------------------------------------------------------------
# Standing operational block (present every quarter, kept short)
# ---------------------------------------------------------------------------
OPS_BLOCK = Block(
    key="ops",
    title="Tribes",
    description="Feedback on our tribes so that we can determine where to focus our effort and energy.",
    questions=(
        Question(
            key="ops.teams",
            type=TYPE_MATRIX,
            label="How are our tribes doing?",
            help=(
                "1 = needs work, 5 = excellent. Choose N/A if you haven't dealt "
                "with them."
            ),
            choices=TEAM_RATING_OPTIONS,
            rows=(),  # populated live from the tribes app — see row_source
            row_source="tribes",
            scale_kind="rating",
            trendable=True,
        ),
        Question(
            key="ops.teams_why",
            type=TYPE_TEXT,
            label="For any tribe that you rated high or low, could you provide a sentence on why?",
        ),
    ),
)

# ---------------------------------------------------------------------------
# Tools & services (rate the platform surfaces you actually use)
# ---------------------------------------------------------------------------
# One satisfaction reading per member-facing service, with N/A so non-users
# skip fast. Per-row trends show which tools are landing over time. The guide
# backlog follows as the natural action item for the Learning Center row —
# we no longer ask "do you understand X?" since completion is measured.
SERVICE_ROWS = (
    ("community", "Community pages (content, story, values)"),
    ("learning", "Learning Center"),
    ("fleets", "Fleet tool"),
    ("fittings", "Fittings & doctrines"),
    ("freight", "Freight service"),
    ("buyback", "Buyback service"),
    ("loyalty", "Loyalty point service"),
    ("orders", "Order service"),
    ("market", "Market services (contracts, sell orders)"),
    ("srp", "Ship replacement (SRP)"),
)

TOOLS_BLOCK = Block(
    key="tools",
    title="Tools & services",
    description="Rate the parts of the platform you use — N/A if you haven't.",
    questions=(
        Question(
            key="tools.rating",
            type=TYPE_MATRIX,
            label="How well do these serve you?",
            help="1 = needs work, 5 = excellent. N/A if you haven't used it.",
            choices=TEAM_RATING_OPTIONS,
            rows=SERVICE_ROWS,
            scale_kind="rating",
            row_filter="service_usage",
            trendable=True,
        ),
    ),
)

# ---------------------------------------------------------------------------
# Content (present every quarter)
# ---------------------------------------------------------------------------
# Rate the quality of each content bracket. To fight recency bias, each rating
# shows recent fleets in that bracket and the FCs who ran them (portraits),
# pulled live — see context_source.
# Quantity is a symmetric 1-5 diverging scale: 3 is the ideal amount, and both
# ends (too little / too much) taper off equally as worse.
QUANTITY_SCALE = ("1", "2", "3", "4", "5")


def _content_pair(bracket: str, word: str, help_text: str):
    group = f"{word[:1].upper()}{word[1:]} content"
    return (
        Question(
            key=f"content.{bracket}.quality",
            type=TYPE_SCALE5,
            label="Quality",
            help=help_text,
            scale_labels=("Poor", "Excellent"),
            context_source=f"content:{bracket}",
            group=group,
            trendable=True,
        ),
        Question(
            key=f"content.{bracket}.quantity",
            type=TYPE_SINGLE,
            label="Quantity",
            help="Whether we run about the right amount of this.",
            choices=QUANTITY_SCALE,
            scale_kind="diverging",
            scale_labels=("Too little", "Too much"),
            group=group,
        ),
    )


CONTENT_BLOCK = Block(
    key="content",
    title="Content",
    description=(
        "Rate the quality and amount of each kind of content. Recent fleets and "
        "the FCs running them are shown to jog your memory across the quarter."
    ),
    questions=(
        *_content_pair(
            "strategic", "strategic", "Strategic ops and the FCs who run them."
        ),
        *_content_pair(
            "non_strategic",
            "non-strategic",
            "Non-strategic fleets, roams, and the FCs who run them.",
        ),
        *_content_pair(
            "training",
            "training",
            "Training fleets and Learning Center resources.",
        ),
        Question(
            key="content.feedback",
            type=TYPE_TEXT,
            label="Any other feedback about our content or fleet commanders?",
        ),
    ),
)

# ---------------------------------------------------------------------------
# Your corporation (present every quarter)
# ---------------------------------------------------------------------------
# About the respondent's experience INSIDE THEIR OWN corp. Auto-scoped: the
# corp is taken from their identity (shown in the profile card), never picked
# from a dropdown. Answers are reported only as per-corp aggregates (the
# corp:NAME segment) — never attributed to an individual, and never a ranking
# of corps against each other or of named people.
CORP_BLOCK = Block(
    key="corp",
    title="Your corporation",
    description=(
        "About your experience inside your own corporation. Reported only as "
        "per-corporation aggregates — never attributed to you."
    ),
    questions=(
        Question(
            key="corp.connection",
            type=TYPE_AGREE,
            label="I feel connected to my corporation.",
            trendable=True,
        ),
        Question(
            key="corp.leadership",
            type=TYPE_AGREE,
            label=(
                "I feel supported by my corporation's leadership and know who "
                "to go to when I need help."
            ),
            trendable=True,
        ),
        Question(
            key="corp.alliance_belonging",
            type=TYPE_AGREE,
            label=(
                "My corporation feels like part of the alliance, not off on "
                "its own."
            ),
            trendable=True,
        ),
        Question(
            key="corp.retention",
            type=TYPE_SCALE5,
            label="How likely are you to still be in this corporation in 3 months?",
            scale_labels=("Very unlikely", "Very likely"),
            trendable=True,
        ),
        Question(
            key="corp.feedback",
            type=TYPE_TEXT,
            label="Anything your corporation's leadership should know?",
        ),
    ),
)

# ---------------------------------------------------------------------------
# Open floor (present every quarter)
# ---------------------------------------------------------------------------
OPEN_BLOCK = Block(
    key="open",
    title="Open floor",
    description="The floor is yours — the more specific, the more we can act on it.",
    questions=(
        Question(
            key="open.focus",
            type=TYPE_TEXT,
            label="In your opinion, what should the alliance focus on more?",
        ),
        Question(
            key="open.tooling",
            type=TYPE_TEXT,
            label="Are there any website or tooling improvements you'd like to see?",
        ),
        Question(
            key="open.anything",
            type=TYPE_TEXT,
            label="Anything else you want leadership to know?",
        ),
        Question(
            key="core.leave_reason",
            type=TYPE_TEXT,
            label="What is the single biggest thing that would make you leave?",
        ),
    ),
)

# ---------------------------------------------------------------------------
# Onboarding (shown only to trial members, every quarter — see audience gate)
# ---------------------------------------------------------------------------
ONBOARDING_BLOCK = Block(
    key="onboarding",
    title="Onboarding",
    description="For members still in their trial period.",
    audience="trial",
    questions=(
        Question(
            key="onboarding.welcomed",
            type=TYPE_AGREE,
            label="I felt welcomed and knew what to do in my first week.",
            trendable=True,
        ),
        Question(
            key="onboarding.friction",
            type=TYPE_TEXT,
            label="What was the most confusing part of getting started?",
        ),
    ),
)
