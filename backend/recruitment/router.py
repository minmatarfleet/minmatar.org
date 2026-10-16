"""Corporation recruitment threads on the EVE Online forums."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
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
