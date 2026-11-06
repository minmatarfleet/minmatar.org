"""Help ticket categories and the panel channel, managed from the site.

The bot-facing routes stay in `help_tickets.router`; these are for the people
who own tickets. Everything here needs the `help_tickets.manage` feature.
"""

from typing import Optional

from django.db import transaction
from django.utils.text import slugify
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from help_tickets.models import HelpRequestCategory, HelpTicketPanel
from tribes.models import TribeGroup

FEATURE = "help_tickets.manage"
FORBIDDEN = "You can't manage help ticket categories."

settings_router = Router(tags=["Help tickets"])


class HelpCategoryResponse(BaseModel):
    id: int
    title: str
    description: str
    code: str
    section: str
    sort_order: int
    is_active: bool
    tribe_group_id: Optional[int] = None
    tribe_group_name: Optional[str] = None
    assignee_names: list[str]


class HelpTribeGroupOption(BaseModel):
    id: int
    name: str
    tribe_name: str
    # Another category already routes to this group.
    taken: bool


class HelpPanelResponse(BaseModel):
    channel_id: int
    message_id: Optional[int] = None


class HelpSettingsResponse(BaseModel):
    categories: list[HelpCategoryResponse]
    tribe_groups: list[HelpTribeGroupOption]
    panel: HelpPanelResponse


class HelpCategoryCreate(BaseModel):
    title: str
    description: str = ""
    section: str = ""
    tribe_group_id: Optional[int] = None


class HelpCategoryPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    section: Optional[str] = None
    tribe_group_id: Optional[int] = None
    is_active: Optional[bool] = None


class HelpCategoryOrder(BaseModel):
    ids: list[int]


class HelpPanelPatch(BaseModel):
    channel_id: int


def _denied(request):
    if can_use_feature(request.user, FEATURE):
        return None
    return 403, ErrorResponse(detail=FORBIDDEN)


def _category_row(category: HelpRequestCategory) -> dict:
    group = category.tribe_group
    return {
        "id": category.id,
        "title": category.title,
        "description": category.description,
        "code": category.code,
        "section": category.section,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "tribe_group_id": group.id if group else None,
        "tribe_group_name": group.name if group else None,
        "assignee_names": [u.username for u in category.assignees.all()],
    }


def _group_error(group_id, own_id=None):
    if not group_id:
        return None
    if not TribeGroup.objects.filter(pk=group_id).exists():
        return "That tribe group does not exist."
    taken = HelpRequestCategory.objects.filter(tribe_group_id=group_id)
    if own_id:
        taken = taken.exclude(pk=own_id)
    if taken.exists():
        return "Another category already routes to that tribe group."
    return None


def _unique_code(title: str) -> str:
    base = slugify(title)[:56] or "category"
    code, n = base, 2
    while HelpRequestCategory.objects.filter(code=code).exists():
        code = f"{base}-{n}"
        n += 1
    return code


@settings_router.get(
    "/settings",
    response={200: HelpSettingsResponse, 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Help ticket categories, tribe groups to route to, and the panel",
)
def get_settings(request):
    if (denied := _denied(request)) is not None:
        return denied
    categories = (
        HelpRequestCategory.objects.select_related("tribe_group")
        .prefetch_related("assignees")
        .order_by("sort_order", "title")
    )
    taken = set(
        HelpRequestCategory.objects.exclude(tribe_group=None).values_list(
            "tribe_group_id", flat=True
        )
    )
    groups = TribeGroup.objects.select_related("tribe").order_by(
        "tribe__name", "name"
    )
    panel = HelpTicketPanel.get_solo()
    return 200, {
        "categories": [_category_row(c) for c in categories],
        "tribe_groups": [
            {
                "id": g.id,
                "name": g.name,
                "tribe_name": g.tribe.name,
                "taken": g.id in taken,
            }
            for g in groups
        ],
        "panel": {
            "channel_id": panel.channel_id,
            "message_id": panel.message_id,
        },
    }


@settings_router.post(
    "/categories",
    response={
        200: HelpCategoryResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Add a help ticket category",
)
def create_category(request, payload: HelpCategoryCreate):
    if (denied := _denied(request)) is not None:
        return denied
    title = payload.title.strip()
    if not title or len(title) > 100:
        return 400, ErrorResponse(detail="Give the category a short title.")
    if error := _group_error(payload.tribe_group_id):
        return 400, ErrorResponse(detail=error)
    last = (
        HelpRequestCategory.objects.order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
    )
    category = HelpRequestCategory(
        title=title,
        description=payload.description.strip(),
        section=payload.section.strip()[:128],
        tribe_group_id=payload.tribe_group_id,
        sort_order=(last or 0) + 10,
    )
    # A tribe-linked category takes the group's code in save().
    if not category.tribe_group_id:
        category.code = _unique_code(title)
    category.save()
    return 200, _category_row(category)


@settings_router.patch(
    "/categories/{category_id}",
    response={
        200: HelpCategoryResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Rename a category, change its owner or turn it off",
)
def patch_category(request, category_id: int, payload: HelpCategoryPatch):
    if (denied := _denied(request)) is not None:
        return denied
    category = (
        HelpRequestCategory.objects.select_related("tribe_group")
        .filter(pk=category_id)
        .first()
    )
    if category is None:
        return 404, ErrorResponse(detail="Category not found.")
    changes = payload.dict(exclude_unset=True)
    if "title" in changes:
        changes["title"] = (changes["title"] or "").strip()
        if not changes["title"] or len(changes["title"]) > 100:
            return 400, ErrorResponse(detail="Give it a short title.")
    if "tribe_group_id" in changes:
        if error := _group_error(changes["tribe_group_id"], category.pk):
            return 400, ErrorResponse(detail=error)
    if changes.get("is_active") is None:
        changes.pop("is_active", None)
    for field in ("description", "section"):
        if field in changes:
            changes[field] = (changes[field] or "").strip()
    for field, value in changes.items():
        setattr(category, field, value)
    category.save()
    category.refresh_from_db()
    return 200, _category_row(category)


@settings_router.post(
    "/category-order",
    response={
        200: list[HelpCategoryResponse],
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Set the order the panel lists categories in",
)
def order_categories(request, payload: HelpCategoryOrder):
    if (denied := _denied(request)) is not None:
        return denied
    existing = set(HelpRequestCategory.objects.values_list("id", flat=True))
    if set(payload.ids) != existing or len(payload.ids) != len(existing):
        return 400, ErrorResponse(
            detail="Send every category exactly once to reorder them."
        )
    with transaction.atomic():
        for position, category_id in enumerate(payload.ids):
            HelpRequestCategory.objects.filter(pk=category_id).update(
                sort_order=(position + 1) * 10
            )
    categories = (
        HelpRequestCategory.objects.select_related("tribe_group")
        .prefetch_related("assignees")
        .order_by("sort_order", "title")
    )
    return 200, [_category_row(c) for c in categories]


@settings_router.patch(
    "/panel",
    response={
        200: HelpPanelResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Set the channel the #help panel is posted in",
)
def patch_panel(request, payload: HelpPanelPatch):
    if (denied := _denied(request)) is not None:
        return denied
    if payload.channel_id <= 0:
        return 400, ErrorResponse(detail="Enter a Discord channel id.")
    panel = HelpTicketPanel.get_solo()
    panel.channel_id = payload.channel_id
    panel.save(update_fields=["channel_id"])
    return 200, {
        "channel_id": panel.channel_id,
        "message_id": panel.message_id,
    }
