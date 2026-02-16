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

MARKET_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-wallet.read_corporation_wallets.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-contracts.read_corporation_contracts.v1",
    "esi-markets.read_character_orders.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-markets.structure_markets.v1",
]

EXECUTOR_SCOPES = [
    "esi-mail.send_mail.v1",
]


class TokenType(Enum):
    DIRECTOR = "Director"
    PUBLIC = "Public"
    BASIC = "Basic"
    INDUSTRY = "Industry"
    MARKET = "Market"
    EXECUTOR = "Executor"


def scopes_for(token_type: TokenType):
    """Returns the full list of scopes for the specified token type (Basic + added groups)."""
    match token_type:
        case TokenType.BASIC:
            return list(BASIC_SCOPES)
        case TokenType.DIRECTOR:
            return BASIC_SCOPES + DIRECTOR_SCOPES
        case TokenType.INDUSTRY:
            return BASIC_SCOPES + INDUSTRY_SCOPES
        case TokenType.PUBLIC:
            return ["publicData"]
        case TokenType.MARKET:
            return BASIC_SCOPES + DIRECTOR_SCOPES + MARKET_SCOPES
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
    if "esi-characters.read_notifications.v1" in token_scopes:
        return TokenType.DIRECTOR.value
    if "esi-characters.read_blueprints.v1" in token_scopes:
        return TokenType.INDUSTRY.value
    if "esi-fleets.read_fleet.v1" in token_scopes:
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


def add_scopes(token_type: TokenType, token: Token):
    for scope_name in scopes_for(token_type):
        scope, _ = Scope.objects.get_or_create(
            name=scope_name,
        )
        token.scopes.add(scope)
