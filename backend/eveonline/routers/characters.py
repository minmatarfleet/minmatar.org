from enum import Enum

from django.shortcuts import redirect
from esi.decorators import token_required
from ninja import Router

router = Router(tags=["Characters"])


class TokenType(Enum):
    CEO = "CEO"
    ALLIANCE = "Alliance"
    ASSOCIATE = "Associate"
    MILITIA = "Militia"
    PUBLIC = "Public"


CEO_SCOPES = [
    "esi-corporations.read_corporation_membership.v1",
    "esi-corporations.read_structures.v1",
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
    "esi-contracts.read_corporation_contracts.v1",
]

MILITIA_SCOPES = [
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
]

ALLIANCE_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-assets.read_assets.v1",
] + MILITIA_SCOPES

ASSOCIATE_SCOPES = [
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
] + ALLIANCE_SCOPES


@router.get("/add", summary="Login with EVE Online")
def add_character(request, redirect_url: str, token_type: TokenType):
    request.session["redirect_url"] = redirect_url
    scopes = None
    match token_type:
        case TokenType.ALLIANCE:
            scopes = ALLIANCE_SCOPES
        case TokenType.ASSOCIATE:
            scopes = ASSOCIATE_SCOPES
        case TokenType.MILITIA:
            scopes = MILITIA_SCOPES
        case TokenType.CEO:
            scopes = CEO_SCOPES
        case TokenType.PUBLIC:
            scopes = []

    @token_required(scopes=scopes, new=True)
    def wrapped(request):
        return redirect(request.session["redirect_url"])

    return wrapped(request)
