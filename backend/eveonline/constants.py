"""Shared eveonline constants.

The one place the backend names our alliances, the holding corporation and
the empire factions. Import these instead of writing the IDs inline; a test
(eveonline.tests.test_identity_constants) fails on new literals elsewhere.
"""

MINMATAR_FLEET_ALLIANCE_ID = 99011978  # ticker FL33T
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

# The alliance holding corporation parks characters and assets; it has no
# members of its own, so alliance health and officer access leave it out.
HOLDING_CORPORATION_TICKER = "MH0LD"

# ESI empire faction IDs (killmails, affiliations, fw/systems).
CALDARI_FACTION_ID = 500001
MINMATAR_FACTION_ID = 500002
AMARR_FACTION_ID = 500003
GALLENTE_FACTION_ID = 500004
