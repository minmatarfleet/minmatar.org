import logging

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
    page: str
    link: str


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
    # User ID to code algorithm: user_id * 83 + 7
    prefix = code[0:1]
    log.info("prefix %s", prefix)
    suffix = int(code[1:])
    user_id = (suffix - 7) / 83
    log.info("user id %d", user_id)

    ReferralClick.objects.create(
        page=page, user_id=user_id, identifier=get_client_ip(request)
    )

    match page:
        case "freight":
            return redirect("https://my.minmatar.org/market/freight/standard/")
        case "plexing":
            return redirect(
                "https://wiki.minmatar.org/alliance/Academy/Faction_Warfare_Plexing"
            )
        case "advantage":
            return redirect(
                "https://wiki.minmatar.org/alliance/Academy/faction-warfare-advantage"
            )
        case "battlefield":
            return redirect("https://wiki.minmatar.org/guides/battlefields")
        case _:
            return redirect("https://my.minmatar.org/badreferral")


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
    return [
        LinkInfo(
            page="Freight",
            link=f"https://api.minmatar.org/api/referrals?page=freight&code={code}",
        ),
        LinkInfo(
            page="Plexing",
            link=f"https://api.minmatar.org/api/referrals?page=plexing&code={code}",
        ),
        LinkInfo(
            page="Advantage",
            link=f"https://api.minmatar.org/api/referrals?page=advantage&code={code}",
        ),
        LinkInfo(
            page="Battlefields",
            link=f"https://api.minmatar.org/api/referrals?page=battlefield&code={code}",
        ),
    ]
