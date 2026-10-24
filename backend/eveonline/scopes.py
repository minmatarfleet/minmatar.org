from enum import Enum
from typing import List

from esi.models import Token, Scope

BASIC_SCOPES = [
    "esi-corporations.read_structures.v1",
    "esi-fleets.read_fleet.v1",
    "esi-fleets.write_fleet.v1",
    "esi-assets.read_assets.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    # Character search covers corporations and alliances, not only structures.
    "esi-search.search_structures.v1",
]

DIRECTOR_SCOPES = [
    "esi-characters.read_notifications.v1",
    "esi-corporations.read_corporation_membership.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-corporations.read_contacts.v1",
    "esi-corporations.read_container_logs.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_facilities.v1",
    "esi-corporations.read_fw_stats.v1",
    "esi-corporations.read_medals.v1",
    "esi-corporations.read_projects.v1",
    "esi-corporations.read_standings.v1",
    "esi-corporations.read_starbases.v1",
    "esi-corporations.read_titles.v1",
    "esi-corporations.track_members.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-killmails.read_corporation_killmails.v1",
    "esi-planets.read_customs_offices.v1",
    "esi-wallet.read_corporation_wallets.v1",
]

INDUSTRY_SCOPES = [
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_agents_research.v1",
    "esi-planets.manage_planets.v1",
    "esi-planets.read_customs_offices.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-industry.read_corporation_mining.v1",
]

# Only what the market tools call: structure order books, attributed orders
# and contracts. Corp wallets stay in Director, where buyback and the wallet
# journal look for them.
MARKET_SCOPES = [
    "esi-contracts.read_character_contracts.v1",
    "esi-contracts.read_corporation_contracts.v1",
    "esi-markets.read_character_orders.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-markets.structure_markets.v1",
]

EXECUTOR_SCOPES = [
    "esi-mail.send_mail.v1",
]

# Lets a fleet commander save fleet refits / custom fits in-game so the
# MOTD can link them. Added on top of Basic.
FLEET_COMMANDER_SCOPES = [
    "esi-fittings.write_fittings.v1",
]

# What campaigns read per pilot: Faction Warfare LP payout notifications, the
# only per-pilot record that a complex, advantage site or battlefield was
# completed. Readiness checks this alone, not the whole Faction Warfare group.
CAMPAIGN_SCOPES = [
    "esi-characters.read_notifications.v1",
]

# FW stats used to sit in Basic. Moving it here shrinks Basic, so every token
# granted before still satisfies Basic and the groups built on it.
FACTION_WARFARE_SCOPES = [
    "esi-characters.read_fw_stats.v1",
    *CAMPAIGN_SCOPES,
]

# What the Minmatar Fleet desktop app uses on the pilot's behalf. Optional, on
# by default in the add-character dialog. UI writes happen only on an explicit
# click, one request per click (docs/desktop/ccp-third-party-guidelines.md,
# rules 2 and 14). Nothing here overlaps another group, so scope_group() can
# tell a Desktop token apart.
DESKTOP_SCOPES = [
    # Set destination: route to the fleet, the form-up or staging.
    "esi-ui.write_waypoint.v1",
    # Open a contract, a market item or a pilot's info window in the client.
    "esi-ui.open_window.v1",
    # Where the pilot is, for jumps to the fleet when no game log is readable.
    "esi-location.read_location.v1",
    # The hull they're in, for the doctrine check before joining a fleet.
    "esi-location.read_ship_type.v1",
    # Which characters are logged in, for picking the one to sign up or route.
    "esi-location.read_online.v1",
    # Jump fatigue, for capital pilots deciding whether they can make a fleet.
    "esi-characters.read_fatigue.v1",
]


class TokenType(Enum):
    DIRECTOR = "Director"
    PUBLIC = "Public"
    BASIC = "Basic"
    INDUSTRY = "Industry"
    MARKET = "Market"
    EXECUTOR = "Executor"
    FLEET_COMMANDER = "FleetCommander"
    FACTION_WARFARE = "FactionWarfare"
    DESKTOP = "Desktop"
    # Legacy name for Faction Warfare. Still stored on characters and in
    # campaign links, so it stays parseable and grants the same scopes.
    CAMPAIGN = "Campaign"


# Requested on top of the asked-for token type whenever a character is added
# without naming one (Add character, Add main). Gates still check the token
# type alone, so older tokens without these keep passing.
NEW_CHARACTER_SCOPE_GROUPS = [TokenType.FACTION_WARFARE]

# Groups a pilot may switch on in the add-character dialog, on top of Basic.
SELECTABLE_SCOPE_GROUPS = (
    TokenType.FACTION_WARFARE,
    TokenType.INDUSTRY,
    TokenType.MARKET,
    TokenType.DESKTOP,
    TokenType.FLEET_COMMANDER,
    TokenType.DIRECTOR,
)


def parse_scope_groups(value: str | None) -> List[TokenType]:
    """Selectable groups named in a comma-separated list, in order, once each.

    Anything else, Executor included, is dropped rather than refused, so an
    old or edited link still signs the pilot in with what it can.
    """
    groups: List[TokenType] = []
    for name in (value or "").split(","):
        try:
            group = TokenType(name.strip())
        except ValueError:
            continue
        if group in SELECTABLE_SCOPE_GROUPS and group not in groups:
            groups.append(group)
    return groups


def scopes_for(token_type: TokenType):
    """Returns the full list of scopes for the specified token type (Basic + added groups)."""
    match token_type:
        case TokenType.BASIC:
            return list(BASIC_SCOPES)
        case TokenType.DIRECTOR:
            return BASIC_SCOPES + DIRECTOR_SCOPES
        case TokenType.INDUSTRY:
            return BASIC_SCOPES + INDUSTRY_SCOPES
        case TokenType.FLEET_COMMANDER:
            return BASIC_SCOPES + FLEET_COMMANDER_SCOPES
        case TokenType.FACTION_WARFARE | TokenType.CAMPAIGN:
            return BASIC_SCOPES + FACTION_WARFARE_SCOPES
        case TokenType.PUBLIC:
            return ["publicData"]
        case TokenType.MARKET:
            return BASIC_SCOPES + MARKET_SCOPES
        case TokenType.DESKTOP:
            return BASIC_SCOPES + DESKTOP_SCOPES
        case TokenType.EXECUTOR:
            return (
                BASIC_SCOPES
                + DIRECTOR_SCOPES
                + MARKET_SCOPES
                + EXECUTOR_SCOPES
            )
        case _:
            return []


def scopes_for_groups(groups: List[str]) -> List[str]:
    """Returns the union of scopes for all given scope groups (no order)."""
    if not groups:
        return []
    result = set()
    for name in groups:
        try:
            token_type = TokenType(name)
        except ValueError:
            continue
        scopes = scopes_for(token_type)
        if scopes:
            result.update(scopes)
    return sorted(result)


def scope_group(token: Token) -> str | None:
    """Returns the widest scope group that the token matches"""
    if not token:
        return None

    token_scopes = scope_names(token)

    if "esi-mail.send_mail.v1" in token_scopes:
        return TokenType.EXECUTOR.value
    if "esi-contracts.read_character_contracts.v1" in token_scopes:
        return TokenType.MARKET.value
    if "esi-contracts.read_corporation_contracts.v1" in token_scopes:
        return TokenType.MARKET.value
    if "esi-markets.structure_markets.v1" in token_scopes:
        return TokenType.MARKET.value
    if "esi-corporations.read_corporation_membership.v1" in token_scopes:
        return TokenType.DIRECTOR.value
    if "esi-characters.read_blueprints.v1" in token_scopes:
        return TokenType.INDUSTRY.value
    if "esi-fittings.write_fittings.v1" in token_scopes:
        return TokenType.FLEET_COMMANDER.value
    # Faction Warfare is the narrowest group that carries notifications. It is
    # tested last, or a pilot who added it on top of Industry would be
    # relabelled and lose their industry scopes on the next re-auth.
    if "esi-characters.read_notifications.v1" in token_scopes:
        return TokenType.FACTION_WARFARE.value
    # Desktop comes after Faction Warfare for the same reason: new characters
    # get both, and the label should stay the group campaigns look for.
    if "esi-ui.write_waypoint.v1" in token_scopes:
        return TokenType.DESKTOP.value
    if "esi-fleets.read_fleet.v1" in token_scopes:
        return TokenType.BASIC.value

    return TokenType.PUBLIC.value


# Widest first, the order scope_group() tests them in.
LISTED_SCOPE_GROUPS = (
    TokenType.EXECUTOR,
    TokenType.MARKET,
    TokenType.DIRECTOR,
    TokenType.INDUSTRY,
    TokenType.FLEET_COMMANDER,
    TokenType.FACTION_WARFARE,
    TokenType.DESKTOP,
)


def scope_groups(token: Token) -> List[str]:
    """Every scope group the token holds, widest first.

    scope_group()'s label always comes first, so a token missing a scope that
    was added to its group later keeps the label it had. The others are listed
    only when the token has all of their scopes. Basic or Public is the only
    entry when nothing wider matches.
    """
    widest = scope_group(token)
    if widest is None:
        return []
    groups = [widest]
    token_scopes = set(scope_names(token))
    for token_type in LISTED_SCOPE_GROUPS:
        if token_type.value not in groups and set(
            scopes_for(token_type)
        ).issubset(token_scopes):
            groups.append(token_type.value)
    return groups


def scope_names(token: Token) -> List[str]:
    token_scopes = []
    for scope in token.scopes.all():
        token_scopes.append(scope.name)
    return sorted(token_scopes)


def token_type_str(s) -> str:
    if s is None:
        return ""
    elif isinstance(s, str):
        return s.removeprefix("TokenType.")
    elif isinstance(s, TokenType):
        return str(s.value)
    else:
        return ""


def add_scopes(token_type: TokenType, token: Token):
    for scope_name in scopes_for(token_type):
        scope, _ = Scope.objects.get_or_create(
            name=scope_name,
        )
        token.scopes.add(scope)


def token_satisfies_type(token: Token, token_type: TokenType) -> bool:
    """True when the token includes every scope for the given token type."""
    if not token:
        return False
    required = set(scopes_for(token_type))
    if not required:
        return False
    return required.issubset(set(scope_names(token)))
