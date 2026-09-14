"""Shared eveonline constants."""

MINMATAR_FLEET_ALLIANCE_ID = 99011978
MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID = 99012009  # ticker BUILD

ALLIED_ALLIANCE_NAMES = [
    "Minmatar Fleet Alliance",
    "Minmatar Fleet Associates",
]

# Alliance + Associates (BUILD) both count as FL33T membership on the site.
FL33T_MEMBER_ALLIANCE_IDS = frozenset(
    {
        MINMATAR_FLEET_ALLIANCE_ID,
        MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
    }
)
