from datetime import datetime
from typing import List

from ninja import Router
from pydantic import BaseModel
from django.core.paginator import Paginator

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import EvePost, EveTag

router = Router(tags=["Posts"])


class EvePostListResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    date_posted: datetime
    user_id: int
    tag_ids: List[int]


class EvePostResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    content: str
    date_posted: datetime
    user_id: int
    tag_ids: List[int]


class EveTagResponse(BaseModel):
    tag_id: int
    tag: str


class CreateEvePostRequest(BaseModel):
    title: str
    state: str
    seo_description: str
    content: str
    tag_ids: List[int]


class UpdateEvePostRequest(BaseModel):
    title: str | None = None
    state: str | None = None
    seo_description: str | None = None
    content: str | None = None
    tag_ids: List[int] | None = None


@router.get("/posts", response=List[EvePostListResponse])
def get_posts(
    request,
    user_id: int = None,
    tag_id: int = None,
    page_size: int = 20,
    page_num: int = None,
):
    posts = EvePost.objects.all().order_by("-date_posted")

    if user_id:
        posts = posts.filter(user_id=user_id)

    if tag_id:
        posts = posts.filter(eveposttag__tag_id=tag_id)

    if page_num:
        paginator = Paginator(posts, per_page=page_size)
        posts = paginator.get_page(page_num)

    response = []
    for post in posts:
        response.append(
            EvePostListResponse(
                post_id=post.id,
                state=post.state,
                seo_description=post.seo_description,
                title=post.title,
                slug=post.slug,
                date_posted=post.date_posted,
                user_id=post.user.id,
                tag_ids=[tag.id for tag in post.tags.all()],
            )
        )
    return response


@router.get("/posts/{post_id}", response=EvePostResponse)
def get_post(request, post_id: int):
    post = EvePost.objects.get(id=post_id)

    return EvePostResponse(
        post_id=post.id,
        state=post.state,
        seo_description=post.seo_description,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        tag_ids=[tag.id for tag in post.tags.all()],
    )


@router.post(
    "/posts",
    response={403: ErrorResponse, 400: ErrorResponse, 200: EvePostResponse},
    auth=AuthBearer(),
)
def create_post(request, payload: CreateEvePostRequest):
    if not request.user.has_perm("posts.add_evepost"):
        return 403, {"detail": "You do not have permission to create a post."}

    if EvePost.objects.filter(title=payload.title).exists():
        return 400, {"detail": "A post with this title already exists."}

    post = EvePost.objects.create(
        title=payload.title,
        state=payload.state,
        seo_description=payload.seo_description,
        slug=EvePost.generate_slug(payload.title),
        content=payload.content,
        user=request.user,
    )
    post.tags.set(EveTag.objects.filter(id__in=payload.tag_ids))

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        state=post.state,
        seo_description=post.seo_description,
        tag_ids=[tag.id for tag in post.tags.all()],
    )


@router.patch(
    "/posts/{post_id}",
    response={403: ErrorResponse, 400: ErrorResponse, 200: EvePostResponse},
    auth=AuthBearer(),
)
def update_post(request, post_id: int, payload: UpdateEvePostRequest):
    if not request.user.has_perm("posts.change_evepost"):
        return 403, {"detail": "You do not have permission to update a post."}

    post = EvePost.objects.get(id=post_id)

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

    post.save()

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
        state=post.state,
        seo_description=post.seo_description,
        tag_ids=[tag.id for tag in post.tags.all()],
    )


@router.delete(
    "/posts/{post_id}",
    response={403: ErrorResponse, 204: None},
    auth=AuthBearer(),
)
def delete_post(request, post_id: int):
    if not request.user.has_perm("posts.delete_evepost"):
        return 403, {"detail": "You do not have permission to delete a post."}

    post = EvePost.objects.get(id=post_id)
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
