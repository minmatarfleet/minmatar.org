from datetime import datetime
from html import unescape
from typing import List
import re

from ninja import Router
from pydantic import BaseModel
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.core.paginator import Paginator

from app.errors import ErrorResponse
from authentication import AuthBearer, AuthOptional
from campaigns.helpers import resolve_attachable_campaign

from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)

from .announce import announce_group_post
from .authors import author_fields_for_main, post_author_fields
from .models import EvePost, EveTag
from groups.helpers.feature_access import can_use_feature
from tribes.helpers.permissions import user_can_manage_group
from tribes.helpers.publishing import (
    KIND_POST,
    can_publish,
    host_group_ref,
    post_visible_to,
    visible_group_ids,
)
from tribes.models import TribeGroup
from tribes.schemas import HostGroupRef, RestrictedResponse, restricted


def _tribe_group_ids(post: EvePost) -> List[int]:
    # .all() reuses prefetch_related("tribe_groups") on list endpoints.
    return [group.id for group in post.tribe_groups.all()]


def _set_tribe_groups(
    post: EvePost, tribe_group_ids: List[int] | None
) -> None:
    if tribe_group_ids is None:
        return
    post.tribe_groups.set(
        TribeGroup.objects.filter(id__in=tribe_group_ids, is_active=True)
    )


def _host_fields(post: EvePost) -> dict:
    return {
        "host_group": (
            host_group_ref(post.host_group) if post.host_group_id else None
        ),
        "members_only": bool(post.members_only),
    }


def _visible_posts_q(user) -> Q:
    """Members-only group posts only for the group, its managers and the
    author (docs/tribes/tribe-publishing.md)."""
    q = Q(members_only=False)
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return q
    if user.is_superuser:
        return Q()
    group_ids = visible_group_ids(user)
    if group_ids:
        q |= Q(host_group_id__in=group_ids)
    return q | Q(user_id=user.pk)


def _resolve_post_host(user, host_group_id: int):
    """The group to post as, or a Ninja error tuple."""
    group = (
        TribeGroup.objects.filter(pk=host_group_id, is_active=True)
        .select_related("tribe")
        .first()
    )
    if group is None:
        return 400, {"detail": f"No tribe group with id {host_group_id}"}
    if not can_publish(user, group, KIND_POST):
        return 403, {"detail": f"You can't post as {group.name}."}
    return group


def _may_edit_group_post(user, post: EvePost) -> bool:
    """A group post's author, or anyone who can manage its group."""
    if post.user_id == user.id:
        return True
    return user_can_manage_group(user, post.host_group)


def _campaign_fields(post: EvePost) -> dict:
    return {
        "campaign_id": post.campaign_id,
        "campaign_slug": post.campaign.slug if post.campaign_id else None,
    }


def _assign_campaign(post: EvePost, campaign_id: int | None):
    resolved = resolve_attachable_campaign(campaign_id)
    if isinstance(resolved, tuple):
        return resolved
    post.campaign = resolved
    return None


def _update_denied(user, post: EvePost | None) -> tuple | None:
    """Why the user may not update this post, or None."""
    if post and post.host_group_id:
        # A group post: its author or the group's managers.
        if not _may_edit_group_post(user, post):
            return 403, {"detail": "You can only update your own posts."}
        return None
    if not can_use_feature(user, "posts.edit"):
        return 403, {"detail": "You do not have permission to update a post."}
    if not post:
        return 404, {"detail": "Post not found."}
    if post.user_id != user.id:
        return 403, {"detail": "You can only update your own posts."}
    return None


def _apply_post_host(user, post: EvePost, payload) -> tuple | None:
    """Apply host_group_id / members_only from an update; None or error."""
    fields = payload.model_fields_set
    if "host_group_id" in fields and payload.host_group_id != (
        post.host_group_id
    ):
        if payload.host_group_id:
            group = _resolve_post_host(user, payload.host_group_id)
            if isinstance(group, tuple):
                return group
            post.host_group = group
        else:
            post.host_group = None
    if "members_only" in fields and payload.members_only is not None:
        post.members_only = payload.members_only
    if post.host_group_id is None:
        post.members_only = False
    elif not post.host_group.allow_alliance_posts:
        post.members_only = True
    return None


def extract_first_image_link(content: str) -> str:
    """
    Extract the first image link from markdown content.

    Looks for patterns like ![image](https://example.com/image.png) and returns the URL.
    Returns an empty string if no image link is found.
    """
    # Pattern to match markdown image syntax: ![alt text](url)
    pattern = r"!\[.*?\]\((https?://[^\s)]+)\)"
    match = re.search(pattern, content)

    if match:
        return unescape(match.group(1))

    bare = re.search(
        r"(https://(?:preview\.redd\.it|external-preview\.redd\.it|"
        r"i\.redd\.it|i\.imgur\.com)/[^\s)]+)",
        content,
    )
    if bare:
        return unescape(bare.group(1))
    return ""


router = Router(tags=["Posts"])


class EvePostListResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    image: str  # Changed from 'content' to 'image'
    date_posted: datetime
    user_id: int
    author_character_id: int
    author_character_name: str
    tag_ids: List[int]
    tribe_group_ids: List[int] = []
    host_group: HostGroupRef | None = None
    members_only: bool = False


class EvePostResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    content: str
    date_posted: datetime
    user_id: int
    author_character_id: int
    author_character_name: str
    tag_ids: List[int]
    tribe_group_ids: List[int] = []
    campaign_id: int | None = None
    campaign_slug: str | None = None
    host_group: HostGroupRef | None = None
    members_only: bool = False


class EveTagResponse(BaseModel):
    tag_id: int
    tag: str


class CreateEvePostRequest(BaseModel):
    title: str
    state: str
    seo_description: str
    content: str
    tag_ids: List[int]
    tribe_group_ids: List[int] = []
    campaign_id: int | None = None
    # Post as a tribe group (needs the group's post right).
    host_group_id: int | None = None
    members_only: bool = False
    # Announce in the group's channel when the post is published (once).
    announce: bool = False


class UpdateEvePostRequest(BaseModel):
    title: str | None = None
    state: str | None = None
    seo_description: str | None = None
    content: str | None = None
    tag_ids: List[int] | None = None
    tribe_group_ids: List[int] | None = None
    campaign_id: int | None = None
    # Left out: unchanged. host_group_id null makes it an alliance post.
    host_group_id: int | None = None
    members_only: bool | None = None
    announce: bool | None = None


@router.get("/posts", response=List[EvePostListResponse], auth=AuthOptional())
def get_posts(
    request: HttpRequest,
    response: HttpResponse,
    user_id: int = None,
    tag_id: int = None,
    tribe_group_id: int = None,
    campaign_id: int = None,
    status: str = None,
    page_size: int = 20,
    page_num: int = None,
):
    posts = (
        EvePost.objects.all()
        .order_by("-date_posted")
        .select_related(
            "user",
            "user__eveplayer",
            "user__eveplayer__primary_character",
            "host_group__tribe",
        )
        .prefetch_related("tags", "tribe_groups")
        .filter(_visible_posts_q(request.user))
    )

    if user_id:
        posts = posts.filter(user_id=user_id)

    if tag_id:
        posts = posts.filter(tags__id=tag_id)

    if tribe_group_id:
        # Hosted by the group, or tagged with it ("Also show on groups").
        posts = posts.filter(
            Q(tribe_groups__id=tribe_group_id)
            | Q(host_group_id=tribe_group_id)
        ).distinct()

    if campaign_id:
        posts = posts.filter(campaign_id=campaign_id)

    if status:
        posts = posts.filter(state=status)

    if page_num:
        paginator = Paginator(posts, per_page=page_size)
        posts = paginator.get_page(page_num)
        response["x-total-count"] = EvePost.objects.filter(
            _visible_posts_q(request.user)
        ).count()

    posts = list(posts)
    mains = primary_characters_for_users(post.user_id for post in posts)
    response = []
    for post in posts:
        # Extract the first image link from the content
        image_link = extract_first_image_link(post.content)
        author_character_id, author_character_name = author_fields_for_main(
            mains.get(post.user_id)
        )

        response.append(
            EvePostListResponse(
                post_id=post.id,
                state=post.state,
                seo_description=post.seo_description,
                title=post.title,
                slug=post.slug,
                image=image_link,  # Use the extracted image link with the new field name 'image'
                date_posted=post.date_posted,
                user_id=post.user.id,
                author_character_id=author_character_id,
                author_character_name=author_character_name,
                tag_ids=[tag.id for tag in post.tags.all()],
                tribe_group_ids=_tribe_group_ids(post),
                **_host_fields(post),
            )
        )
    return response


@router.get(
    "/posts/{post_id}",
    response={
        200: EvePostResponse,
        403: RestrictedResponse,
        404: ErrorResponse,
    },
    auth=AuthOptional(),
)
def get_post(request, post_id: int):
    post = (
        EvePost.objects.filter(id=post_id)
        .select_related(
            "user",
            "user__eveplayer",
            "user__eveplayer__primary_character",
            "campaign",
            "host_group__tribe",
        )
        .prefetch_related("tags", "tribe_groups")
        .first()
    )
    if post is None:
        return 404, {"detail": "Post not found"}
    if not post_visible_to(request.user, post):
        return restricted(host_group_ref(post.host_group))

    author_character_id, author_character_name = post_author_fields(post.user)

    return EvePostResponse(
        post_id=post.id,
        state=post.state,
        seo_description=post.seo_description,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        author_character_id=author_character_id,
        author_character_name=author_character_name,
        tag_ids=[tag.id for tag in post.tags.all()],
        tribe_group_ids=_tribe_group_ids(post),
        **_campaign_fields(post),
        **_host_fields(post),
    )


@router.post(
    "/posts",
    response={403: ErrorResponse, 400: ErrorResponse, 200: EvePostResponse},
    auth=AuthBearer(),
)
def create_post(request, payload: CreateEvePostRequest):
    host_group = None
    if payload.host_group_id:
        # A group post needs the group's post right instead of posts.create.
        host_group = _resolve_post_host(request.user, payload.host_group_id)
        if isinstance(host_group, tuple):
            return host_group
    elif not can_use_feature(request.user, "posts.create"):
        return 403, {"detail": "You do not have permission to create a post."}

    if EvePost.objects.filter(title=payload.title).exists():
        return 400, {"detail": "A post with this title already exists."}

    campaign = resolve_attachable_campaign(payload.campaign_id)
    if isinstance(campaign, tuple):
        return campaign

    post = EvePost.objects.create(
        title=payload.title,
        state=payload.state,
        seo_description=payload.seo_description,
        slug=EvePost.generate_slug(payload.title),
        content=payload.content,
        user=request.user,
        campaign=campaign,
        host_group=host_group,
        members_only=bool(
            host_group
            and (payload.members_only or not host_group.allow_alliance_posts)
        ),
    )
    post.tags.set(EveTag.objects.filter(id__in=payload.tag_ids))
    _set_tribe_groups(post, payload.tribe_group_ids)
    if payload.announce:
        announce_group_post(post)
    author_character_id, author_character_name = post_author_fields(post.user)

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        state=post.state,
        seo_description=post.seo_description,
        author_character_id=author_character_id,
        author_character_name=author_character_name,
        tag_ids=[tag.id for tag in post.tags.all()],
        tribe_group_ids=_tribe_group_ids(post),
        **_campaign_fields(post),
        **_host_fields(post),
    )


@router.patch(
    "/posts/{post_id}",
    response={
        403: ErrorResponse,
        400: ErrorResponse,
        200: EvePostResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
)
def update_post(request, post_id: int, payload: UpdateEvePostRequest):
    post = (
        EvePost.objects.filter(id=post_id)
        .select_related("host_group__tribe")
        .first()
    )
    error = _update_denied(request.user, post) or _apply_post_host(
        request.user, post, payload
    )
    if error:
        return error

    if payload.title:
        post.title = payload.title
        post.slug = EvePost.generate_slug(payload.title)

    if payload.state:
        post.state = payload.state

    if payload.seo_description:
        post.seo_description = payload.seo_description

    if payload.content:
        post.content = payload.content

    if payload.tag_ids:
        post.tags.set(EveTag.objects.filter(id__in=payload.tag_ids))

    if payload.tribe_group_ids is not None:
        _set_tribe_groups(post, payload.tribe_group_ids)

    if "campaign_id" in payload.model_fields_set:
        error = _assign_campaign(post, payload.campaign_id)
        if error:
            return error

    post.save()
    if payload.announce:
        announce_group_post(post)
    author_character_id, author_character_name = post_author_fields(post.user)

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        state=post.state,
        seo_description=post.seo_description,
        author_character_id=author_character_id,
        author_character_name=author_character_name,
        tag_ids=[tag.id for tag in post.tags.all()],
        tribe_group_ids=_tribe_group_ids(post),
        **_campaign_fields(post),
        **_host_fields(post),
    )


@router.delete(
    "/posts/{post_id}",
    response={403: ErrorResponse, 404: ErrorResponse, 204: None},
    auth=AuthBearer(),
)
def delete_post(request, post_id: int):
    post = EvePost.objects.filter(id=post_id).first()
    if post and post.host_group_id:
        # A group post: its author or the group's managers.
        if not _may_edit_group_post(request.user, post):
            return 403, {"detail": "You can only delete your own posts."}
        post.delete()
        return 204, None

    if not can_use_feature(request.user, "posts.delete"):
        return 403, {"detail": "You do not have permission to delete a post."}
    if not post:
        return 404, {"detail": "Post not found."}
    if post.user_id != request.user.id:
        return 403, {"detail": "You can only delete your own posts."}

    post.delete()
    return 204, None


@router.get("/tags", response=List[EveTagResponse])
def get_tags(request):
    tags = EveTag.objects.all()
    response = []
    for tag in tags:
        response.append(
            EveTagResponse(
                tag_id=tag.id,
                tag=tag.tag,
            )
        )
    return response
