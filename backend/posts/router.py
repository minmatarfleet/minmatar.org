from datetime import datetime
from typing import List
import re
import base64
import json

from ninja import Router
from pydantic import BaseModel
from django.http import HttpRequest, HttpResponse
from django.core.paginator import Paginator

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import EvePost, EveTag


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
        return match.group(1)
    return ""


def extract_all_image_links(content: str) -> List[str]:
    """
    Extract ALL image links from markdown content.
    
    Looks for patterns like ![image](https://example.com/image.png) and returns all URLs.
    Returns an empty list if no image links are found.
    """
    # Pattern to match markdown image syntax: ![alt text](url)
    pattern = r"!\[.*?\]\((https?://[^\s)]+)\)"
    matches = re.findall(pattern, content)
    return matches


def generate_cursor(post_date: datetime, post_id: int, image_index: int) -> str:
    """
    Generate a cursor for pagination based on post date, ID, and image index.
    """
    cursor_data = {
        "date": post_date.isoformat(),
        "post_id": post_id,
        "image_index": image_index
    }
    cursor_json = json.dumps(cursor_data, sort_keys=True)
    return base64.b64encode(cursor_json.encode()).decode()


def parse_cursor(cursor: str) -> dict:
    """
    Parse a cursor string back into its components.
    """
    try:
        cursor_json = base64.b64decode(cursor.encode()).decode()
        return json.loads(cursor_json)
    except (ValueError, json.JSONDecodeError):
        return None


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


class GalleryImageResponse(BaseModel):
    image_url: str
    post_id: int
    post_title: str
    post_slug: str
    date_posted: datetime
    user_id: int
    image_index: int
    cursor_id: str


class GalleryResponse(BaseModel):
    images: List[GalleryImageResponse]
    next_cursor: str | None = None
    has_more: bool


@router.get("/posts", response=List[EvePostListResponse])
def get_posts(
    request: HttpRequest,
    response: HttpResponse,
    user_id: int = None,
    tag_id: int = None,
    status: str = None,
    page_size: int = 20,
    page_num: int = None,
):
    posts = EvePost.objects.all().order_by("-date_posted")

    if user_id:
        posts = posts.filter(user_id=user_id)

    if tag_id:
        posts = posts.filter(eveposttag__tag_id=tag_id)

    if status:
        posts = posts.filter(state=status)

    if page_num:
        paginator = Paginator(posts, per_page=page_size)
        posts = paginator.get_page(page_num)
        response["x-total-count"] = EvePost.objects.count()

    response = []
    for post in posts:
        # Extract the first image link from the content
        image_link = extract_first_image_link(post.content)

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


@router.get("/gallery", response=GalleryResponse)
def get_gallery_images(
    request: HttpRequest,
    # Cursor Pagination
    limit: int = 30,
    cursor: str = None,

    # Content Filtering
    user_id: int = None,
    tag_id: int = None,
    status: str = "published",
    date_from: str = None,
    date_to: str = None,

    # Gallery Options
    sort_by: str = "date_desc",
    include_metadata: bool = True,
):
    """
    Get images from blog posts for gallery display with cursor-based pagination.

    This endpoint extracts all images from published blog posts and returns them
    in a flattened format suitable for endless scroll galleries.
    """
    # Build base queryset
    posts = EvePost.objects.filter(state=status).order_by("-date_posted")

    # Apply filters
    if user_id:
        posts = posts.filter(user_id=user_id)

    if tag_id:
        posts = posts.filter(eveposttag__tag_id=tag_id)

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            posts = posts.filter(date_posted__gte=from_date)
        except ValueError:
            pass  # Invalid date format, ignore filter

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            posts = posts.filter(date_posted__lte=to_date)
        except ValueError:
            pass  # Invalid date format, ignore filter

    # Apply sorting
    if sort_by == "date_asc":
        posts = posts.order_by("date_posted")
    elif sort_by == "title_asc":
        posts = posts.order_by("title")
    elif sort_by == "random":
        posts = posts.order_by("?")
    else:  # default: date_desc
        posts = posts.order_by("-date_posted")

    # Handle cursor-based pagination
    cursor_data = None
    if cursor:
        cursor_data = parse_cursor(cursor)
        if cursor_data:
            cursor_date = datetime.fromisoformat(cursor_data["date"])
            cursor_post_id = cursor_data["post_id"]

            # Filter posts based on cursor position
            if sort_by == "date_asc":
                posts = posts.filter(
                    date_posted__gt=cursor_date
                ) | posts.filter(
                    date_posted=cursor_date,
                    id__gt=cursor_post_id
                )
            else:  # date_desc or other sorting
                posts = posts.filter(
                    date_posted__lt=cursor_date
                ) | posts.filter(
                    date_posted=cursor_date,
                    id__lt=cursor_post_id
                )

    # Collect images from posts
    gallery_images = []
    posts_processed = 0
    max_posts_to_check = limit * 3  # Check more posts to ensure we get enough images

    for post in posts[:max_posts_to_check]:
        posts_processed += 1
        images = extract_all_image_links(post.content)

        for idx, image_url in enumerate(images):
            # Skip images before cursor position if we're continuing from a cursor
            if cursor_data and post.id == cursor_data["post_id"] and idx <= cursor_data["image_index"]:
                continue

            cursor_id = generate_cursor(post.date_posted, post.id, idx)

            gallery_image = GalleryImageResponse(
                image_url=image_url,
                post_id=post.id,
                post_title=post.title if include_metadata else "",
                post_slug=post.slug if include_metadata else "",
                date_posted=post.date_posted,
                user_id=post.user.id if include_metadata else 0,
                image_index=idx,
                cursor_id=cursor_id
            )

            gallery_images.append(gallery_image)

            # Stop when we have enough images
            if len(gallery_images) >= limit:
                break

        # Stop when we have enough images
        if len(gallery_images) >= limit:
            break

    # Determine if there are more images
    has_more = len(gallery_images) == limit and posts_processed < posts.count()

    # Generate next cursor
    next_cursor = None
    if has_more and gallery_images:
        last_image = gallery_images[-1]
        next_cursor = last_image.cursor_id

    return GalleryResponse(
        images=gallery_images,
        next_cursor=next_cursor,
        has_more=has_more
    )
