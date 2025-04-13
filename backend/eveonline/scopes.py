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
    "esi-characters.read_fw_stats.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
]

ADVANCED_SCOPES = [
    "esi-characters.read_blueprints.v1",
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
] + BASIC_SCOPES

CEO_SCOPES = [
    "esi-corporations.read_corporation_membership.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-corporations.read_contacts.v1",
    "esi-corporations.read_container_logs.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_facilities.v1",
    "esi-corporations.read_fw_stats.v1",
    "esi-corporations.read_medals.v1",
    "esi-corporations.read_starbases.v1",
    "esi-corporations.read_titles.v1",
    "esi-wallet.read_corporation_wallets.v1",
] + ADVANCED_SCOPES

# Used for the freight CEO (Minmatar Fleet Logistics)
FREIGHT_CHARACTER_SCOPES = [
    "esi-contracts.read_corporation_contracts.v1"
] + CEO_SCOPES

# Used for supply team seeders (characters, build corporations)
MARKET_CHARACTER_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-markets.read_character_orders.v1",
    "esi-contracts.read_character_contracts.v1",
] + FREIGHT_CHARACTER_SCOPES

EXECUTOR_CHARACTER_SCOPES = (
    [
        "esi-mail.send_mail.v1",
    ]
    + CEO_SCOPES
    + MARKET_CHARACTER_SCOPES
)


class TokenType(Enum):
    CEO = "CEO"
    PUBLIC = "Public"
    BASIC = "Basic"
    ADVANCED = "Advanced"
    MARKET = "Market"
    FREIGHT = "Freight"
    EXECUTOR = "Executor"


def scopes_for(token_type: TokenType):
    """Returns the list of scopes for the specified token type"""
    scopes = None
    match token_type:
        case TokenType.BASIC:
            scopes = BASIC_SCOPES
        case TokenType.ADVANCED:
            scopes = ADVANCED_SCOPES
        case TokenType.PUBLIC:
            scopes = ["publicData"]
        case TokenType.CEO:
            scopes = CEO_SCOPES
        case TokenType.FREIGHT:
            scopes = FREIGHT_CHARACTER_SCOPES
        case TokenType.MARKET:
            scopes = MARKET_CHARACTER_SCOPES
        case TokenType.EXECUTOR:
            scopes = EXECUTOR_CHARACTER_SCOPES
    return scopes


def scope_group(token: Token) -> str | None:
    """Returns the widest scope group that the token matches"""
    if not Token:
        return None

    token_scopes = scope_names(token)

    if token_scopes == sorted(EXECUTOR_CHARACTER_SCOPES):
        return TokenType.EXECUTOR.value
    if token_scopes == sorted(MARKET_CHARACTER_SCOPES):
        return TokenType.MARKET.value
    if token_scopes == sorted(FREIGHT_CHARACTER_SCOPES):
        return TokenType.FREIGHT.value
    if token_scopes == sorted(CEO_SCOPES):
        return TokenType.CEO.value
    if token_scopes == sorted(ADVANCED_SCOPES):
        return TokenType.ADVANCED.value
    if token_scopes == sorted(BASIC_SCOPES):
        return TokenType.BASIC.value

    return TokenType.PUBLIC.value


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


def add_scopes(tokenType: TokenType, token: Token):
    for scope_name in scopes_for(tokenType):
        scope, _ = Scope.objects.get_or_create(
            name=scope_name,
        )
        token.scopes.add(scope)