"""Moderation endpoints for creator accounts and items.

Backed by the creators.moderate pilot feature. Every action writes an audit
entry; Django admin stays as break-glass.
"""

from django.db.models import Count, Q
from ninja import Router, Schema

from app.errors import ErrorResponse
from audit.helpers import record_audit
from authentication import AuthBearer
from creators.models import CreatorAccount, CreatorAccountStatus, CreatorItem
from groups.helpers.feature_access import require_feature

FEATURE_MODERATE = "creators.moderate"

router = Router(tags=["Creators moderation"], auth=AuthBearer())


class ModerationAccountSchema(Schema):
    id: int
    user_id: int
    username: str
    provider: str
    platform_username: str
    status: str
    item_count: int
    hidden_count: int
    featured_count: int


class ModerationItemSchema(Schema):
    id: int
    account_id: int
    provider: str
    kind: str
    title: str
    url: str
    published_at: str | None = None
    hidden: bool
    featured: bool


class ModerationStatusRequest(Schema):
    status: str


class ModerationItemRequest(Schema):
    hidden: bool | None = None
    featured: bool | None = None


def _account_schema(account) -> ModerationAccountSchema:
    return ModerationAccountSchema(
        id=account.pk,
        user_id=account.user_id,
        username=account.user.username,
        provider=account.provider,
        platform_username=account.platform_username,
        status=account.status,
        item_count=account.item_count,
        hidden_count=account.hidden_count,
        featured_count=account.featured_count,
    )


def _accounts():
    return (
        CreatorAccount.objects.select_related("user")
        .annotate(
            item_count=Count("items"),
            hidden_count=Count("items", filter=Q(items__hidden=True)),
            featured_count=Count("items", filter=Q(items__featured=True)),
        )
        .order_by("provider", "platform_username", "id")
    )


def _item_schema(item: CreatorItem) -> ModerationItemSchema:
    return ModerationItemSchema(
        id=item.pk,
        account_id=item.account_id,
        provider=item.provider,
        kind=item.kind,
        title=item.title,
        url=item.url,
        published_at=(
            item.published_at.isoformat() if item.published_at else None
        ),
        hidden=item.hidden,
        featured=item.featured,
    )


@router.get(
    "accounts",
    response={200: list[ModerationAccountSchema], 403: dict},
    summary="List every creator account with its moderation status.",
)
def list_accounts(request):
    if denied := require_feature(request.user, FEATURE_MODERATE):
        return denied
    return [_account_schema(a) for a in _accounts()]


@router.put(
    "accounts/{account_id}/status",
    response={
        200: ModerationAccountSchema,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Approve or suspend a creator account.",
)
def set_account_status(
    request, account_id: int, payload: ModerationStatusRequest
):
    if denied := require_feature(request.user, FEATURE_MODERATE):
        return denied
    if payload.status not in CreatorAccountStatus.values:
        return 400, ErrorResponse(
            detail="Status must be approved or suspended."
        )
    account = _accounts().filter(pk=account_id).first()
    if account is None:
        return 404, ErrorResponse(detail="Creator account not found.")
    if account.status != payload.status:
        CreatorAccount.objects.filter(pk=account.pk).update(
            status=payload.status
        )
        account.status = payload.status
        record_audit(
            request.user,
            f"Set creator account {account.provider}:"
            f"{account.platform_username or account.platform_user_id} "
            f"to {payload.status}",
        )
    return _account_schema(account)


@router.get(
    "accounts/{account_id}/items",
    response={200: list[ModerationItemSchema], 403: dict, 404: ErrorResponse},
    summary="List a creator account's items, hidden ones included.",
)
def list_items(request, account_id: int):
    if denied := require_feature(request.user, FEATURE_MODERATE):
        return denied
    account = CreatorAccount.objects.filter(pk=account_id).first()
    if account is None:
        return 404, ErrorResponse(detail="Creator account not found.")
    return [_item_schema(i) for i in account.items.all()[:100]]


@router.put(
    "items/{item_id}",
    response={200: ModerationItemSchema, 403: dict, 404: ErrorResponse},
    summary="Feature or hide a creator item.",
)
def update_item(request, item_id: int, payload: ModerationItemRequest):
    if denied := require_feature(request.user, FEATURE_MODERATE):
        return denied
    item = CreatorItem.objects.filter(pk=item_id).first()
    if item is None:
        return 404, ErrorResponse(detail="Creator item not found.")
    changes = []
    for field in ("hidden", "featured"):
        value = getattr(payload, field)
        if value is not None and value != getattr(item, field):
            setattr(item, field, value)
            changes.append(f"{field}={value}")
    if changes:
        item.save(update_fields=["hidden", "featured", "updated_at"])
        record_audit(
            request.user,
            f"Creator item {item.pk} ({item.title[:60]}): "
            + ", ".join(changes),
        )
    return _item_schema(item)
