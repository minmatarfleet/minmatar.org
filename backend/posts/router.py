from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import EvePost, EvePostTag, EveTag

router = Router(tags=["Posts"])


class EvePostListResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    date_posted: str
    user_id: int
    tag_ids: List[int]


class EvePostResponse(BaseModel):
    post_id: int
    state: str
    title: str
    seo_description: str
    slug: str
    content: str
    date_posted: str
    user_id: int
    tag_ids: List[int]


class EveTagesponse(BaseModel):
    tag_id: int
    tag: str


class CreateEvePosRequest(BaseModel):
    title: str
    state: str
    seo_description: str
    content: str


@router.get("/posts", response=List[EvePostListResponse])
def get_posts(request, user_id: int = None, tag_id: int = None):
    posts = EvePost.objects.all().order_by("-date_posted")

    if user_id:
        posts = posts.filter(user_id=user_id)

    if tag_id:
        posts = posts.filter(eveposttag__tag_id=tag_id)

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
                tag_ids=[
                    tag.tag.id for tag in EvePostTag.objects.filter(post=post)
                ],
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
        tag_ids=[tag.tag.id for tag in EvePostTag.objects.filter(post=post)],
    )


@router.post(
    "/posts",
    response={403: ErrorResponse, 400: ErrorResponse, 200: EvePostResponse},
    auth=AuthBearer(),
)
def create_post(request, payload: CreateEvePosRequest):
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

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
    )


@router.put(
    "/posts/{post_id}",
    response={403: ErrorResponse, 400: ErrorResponse, 200: EvePostResponse},
    auth=AuthBearer(),
)
def update_post(request, post_id: int, payload: CreateEvePosRequest):
    if not request.user.has_perm("posts.change_evepost"):
        return 403, {"detail": "You do not have permission to update a post."}

    if EvePost.objects.filter(title=payload.title).exists():
        return 400, {"detail": "A post with this title already exists."}

    post = EvePost.objects.get(id=post_id)
    post.title = payload.title
    post.content = payload.content
    post.seo_description = payload.seo_description
    post.slug = EvePost.generate_slug(payload.title)
    post.state = payload.state
    post.save()

    return EvePostResponse(
        post_id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        date_posted=post.date_posted,
        user_id=post.user.id,
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


@router.get("/tags", response=List[EveTagesponse])
def get_tags(request):
    tags = EveTag.objects.all()
    response = []
    for tag in tags:
        response.append(
            EveTagesponse(
                tag_id=tag.id,
                tag=tag.tag,
            )
        )
    return response
