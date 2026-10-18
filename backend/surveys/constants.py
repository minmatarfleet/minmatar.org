"""Shared constants for the surveys app."""

# Campaign lifecycle
STATUS_DRAFT = "draft"
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_CHOICES = (
    (STATUS_DRAFT, "Draft"),
    (STATUS_OPEN, "Open"),
    (STATUS_CLOSED, "Closed"),
)

# Question types
TYPE_SCALE5 = "scale5"  # 1-5 labelled scale
TYPE_ENPS = "enps"  # 0-10 recommend score
TYPE_AGREE = "agree"  # 5-point agreement scale
TYPE_SINGLE = "single"  # single choice
TYPE_MULTI = "multi"  # multiple choice
TYPE_MATRIX = "matrix"  # rows x options grid
TYPE_TEXT = "text"  # free text

NUMERIC_TYPES = (TYPE_SCALE5, TYPE_ENPS, TYPE_AGREE)

# Tenure cohorts (days)
COHORT_NEW = "<30d"
COHORT_EARLY = "1-3mo"
COHORT_ESTABLISHED = "3-12mo"
COHORT_VETERAN = "1yr+"

# Activity tiers (distinct fleets attended in the trailing quarter). The
# corporation page's member tiers use the same table
# (eveonline.helpers.corporations.summary).
ACTIVITY_CORE = "core"  # 10+
ACTIVITY_REGULAR = "regular"  # 3-9
ACTIVITY_LAPSING = "lapsing"  # 1-2
ACTIVITY_INACTIVE = "inactive"  # 0
ACTIVITY_LAPSING_MAX_FLEETS = 2
ACTIVITY_REGULAR_MAX_FLEETS = 9


def activity_tier(fleet_count: int) -> str:
    """The activity tier for a count of fleets attended."""
    if fleet_count <= 0:
        return ACTIVITY_INACTIVE
    if fleet_count <= ACTIVITY_LAPSING_MAX_FLEETS:
        return ACTIVITY_LAPSING
    if fleet_count <= ACTIVITY_REGULAR_MAX_FLEETS:
        return ACTIVITY_REGULAR
    return ACTIVITY_CORE


# Segment key used for the "everyone" aggregate row
SEGMENT_ALL = "all"

# Feature gate for leadership survey management
FEATURE_MANAGE = "surveys.manage"
