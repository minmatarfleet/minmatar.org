import logging
import hashlib

from typing import List
from ninja import Router
from pydantic import BaseModel
from django.shortcuts import redirect

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import ReferralClick

router = Router(tags=["Referral Links"])

log = logging.getLogger(__name__)


class LinkInfo(BaseModel):
    name: str
    link: str = ""
    target: str = ""


class LinkStats(BaseModel):
    name: str
    user_id: int = 0
    referrals: int = 0


links = [
    LinkInfo(
        name="Corps",
        target="https://my.minmatar.org/alliance/corporations/list/",
    ),
    LinkInfo(
        name="Freight",
        target="https://my.minmatar.org/market/freight/standard/",
    ),
    LinkInfo(
        name="Plexing",
        target="https://wiki.minmatar.org/alliance/Academy/Faction_Warfare_Plexing",
    ),
    LinkInfo(
        name="Advantage",
        target="https://wiki.minmatar.org/alliance/Academy/faction-warfare-advantage",
    ),
    LinkInfo(
        name="Battlefields",
        target="https://wiki.minmatar.org/guides/battlefields",
    ),
]


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


@router.get("", description="Redirect referral link to final destination")
def referral_redirect(request, page: str, code: str):

    # Very rudimentary masking of the user id.
    # The prefix (currently "Q") specifies the algorithm to use.
    # User ID to code algorithm: user_id * 83 + 7.
    prefix = code[0:1]
    suffix = int(code[1:])
    user_id = (suffix - 7) / 83

    hasher = hashlib.sha256()
    hasher.update(str.encode(get_client_ip(request)))
    client_id = hasher.hexdigest()

    log.info(
        "Referral prefix=%s, user=%d, page=%s, client=%s",
        prefix,
        user_id,
        page,
        client_id,
    )

    target = ""
    for link in links:
        if page.lower() == link.name.lower():
            target = link.target

    if target == "":
        log.info("Could not find target for %s", page)
        return redirect("https://my.minmatar.org/badreferral")
    else:
        ReferralClick.objects.create(
            page=page, user_id=user_id, identifier=client_id
        )
        return redirect(target)


@router.get(
    "/links",
    response={
        200: List[LinkInfo],
        403: ErrorResponse,
    },
    description="Show referral links for user",
    auth=AuthBearer(),
)
def get_user_links(request) -> List[LinkInfo]:
    code = "Q" + str(request.user.id * 83 + 7)
    userlinks = []
    for link in links:
        userlink = LinkInfo(
            name=link.name,
            link=request.build_absolute_uri("/api/referrals")
            + "?code="
            + code
            + "&page="
            + link.name,
            target=link.target,
        )

        userlinks.append(userlink)
    return userlinks


@router.get(
    "/stats",
    response={
        200: List[LinkStats],
        403: ErrorResponse,
    },
    description="Show referral stats for user",
    auth=AuthBearer(),
)
def get_link_stats(request) -> List[LinkStats]:
    stats_map = {}

    for referral in ReferralClick.objects.filter(user_id=request.user.id):
        if referral.page not in stats_map:
            stats_map[referral.page] = LinkStats(
                name=referral.page, referrals=0
            )
        stats_map[referral.page].referrals += 1

    stats = []
    for stat in stats_map.values():
        stats.append(stat)

    return stats
