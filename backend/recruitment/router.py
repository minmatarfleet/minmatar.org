"""Corporation recruitment threads and recruitment scout click tracking."""

from typing import List

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from eveonline.helpers.corporations.permissions import user_is_ceo
from eveonline.helpers.corporations.profile import load_corporation
from recruitment.forum_posts import (
    ForumPostError,
    forum_post_settings,
    remove_forum_post,
    save_forum_post,
)
from recruitment.schemas import (
    CorporationForumPost,
    CorporationForumPostUpdate,
    ScoutClickRequest,
    ScoutOutreachRequest,
    ScoutOutreachResponse,
)
from recruitment.scout_links import (
    outreach_stats,
    record_click,
    register_outreach,
    tracked_base_url,
)

router = Router(tags=["Recruitment"])


def _ceo_corporation(request, corporation_id: int):
    """(corporation, None) for the CEO, else (None, error response)."""
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return None, (404, ErrorResponse(detail="Corporation not found"))
    if not user_is_ceo(request.user, corporation):
        return None, (403, ErrorResponse(detail="Only the CEO can do this"))
    return corporation, None


@router.get(
    "/corporations/{corporation_id}/forum-post",
    response={
        200: CorporationForumPost,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="The corporation's EVE forums recruitment thread (CEO only)",
)
def get_corporation_forum_post(request, corporation_id: int):
    corporation, error = _ceo_corporation(request, corporation_id)
    if error:
        return error
    return forum_post_settings(corporation)


@router.put(
    "/corporations/{corporation_id}/forum-post",
    response={
        200: CorporationForumPost,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Link, change or (with an empty url) remove the corporation's "
    "EVE forums recruitment thread (CEO only)",
)
def put_corporation_forum_post(
    request, corporation_id: int, payload: CorporationForumPostUpdate
):
    corporation, error = _ceo_corporation(request, corporation_id)
    if error:
        return error
    if not payload.url.strip():
        remove_forum_post(corporation)
        return forum_post_settings(corporation)
    try:
        save_forum_post(corporation, payload.url, request.user)
    except ForumPostError as e:
        return 400, ErrorResponse(detail=e.code)
    return forum_post_settings(corporation)


@router.delete(
    "/corporations/{corporation_id}/forum-post",
    response={
        200: CorporationForumPost,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Remove the corporation's EVE forums recruitment thread "
    "(CEO only)",
)
def delete_corporation_forum_post(request, corporation_id: int):
    corporation, error = _ceo_corporation(request, corporation_id)
    if error:
        return error
    remove_forum_post(corporation)
    return forum_post_settings(corporation)


@router.post(
    "/scout/outreach",
    response={
        200: ScoutOutreachResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Register a scout reply and get its tracked link base. "
    "Drafting again for the same thread returns the same code.",
)
def post_scout_outreach(request, payload: ScoutOutreachRequest):
    denied = require_feature(request.user, "recruitment.scout")
    if denied:
        return denied
    thread_url = payload.thread_url.strip()
    try:
        URLValidator(schemes=["http", "https"])(thread_url)
    except ValidationError:
        return 400, ErrorResponse(detail="thread_url must be a web URL")
    outreach = register_outreach(
        surface=payload.surface,
        thread_url=thread_url[:500],
        prospect=payload.prospect.strip()[:100],
        seat=payload.seat.strip()[:64],
        user=request.user,
    )
    return {
        "code": outreach.code,
        "surface": outreach.surface,
        "thread_url": outreach.thread_url,
        "prospect": outreach.prospect,
        "seat": outreach.seat,
        "created_at": outreach.created_at,
        "link_base": tracked_base_url(outreach.code),
    }


@router.get(
    "/scout/outreach",
    response={200: List[ScoutOutreachResponse], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Scout replies from the last `days` with unique human "
    "visitors per tracked link",
)
def get_scout_outreach(request, days: int = 30):
    denied = require_feature(request.user, "recruitment.scout")
    if denied:
        return denied
    return outreach_stats(max(1, min(days, 365)))


@router.post(
    "/scout/clicks",
    response={201: str, 404: ErrorResponse},
    summary="Record a visit through a scout reply's tracked link. Called "
    "by the my.minmatar.org /go/ redirect.",
)
def post_scout_click(request, payload: ScoutClickRequest):
    click = record_click(
        code=payload.code,
        target=payload.target,
        client_ip=payload.client_ip,
        user_agent=payload.user_agent,
    )
    if click is None:
        return 404, ErrorResponse(detail="Unknown scout link")
    return 201, "OK"
