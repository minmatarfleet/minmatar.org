import logging
from typing import List

from django.conf import settings
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import UserSubscription

router = Router(tags=["Subscriptions"])

log = logging.getLogger(__name__)


class Subscription(BaseModel):
    id: int = None
    user_id: int = None
    subscription: str


def map_sub(sub: UserSubscription) -> Subscription:
    return Subscription(
        id=sub.id,
        user_id=sub.user.id,
        subscription=sub.subscription,
    )


@router.get(
    "/",
    response={200: List[Subscription], 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Returns subscriptions for the authenticated user. Pass user_id only if you are a superuser.",
)
def get_subscriptions(request, user_id: int = None):
    if user_id is not None and user_id != request.user.id:
        if not request.user.is_superuser:
            return 403, ErrorResponse(
                detail="You can only view your own subscriptions."
            )
    target_id = (
        user_id
        if (user_id is not None and request.user.is_superuser)
        else request.user.id
    )
    query = UserSubscription.objects.filter(user__id=target_id)
    response = [map_sub(sub) for sub in query]
    return response


@router.post(
    "/",
    response={201: Subscription, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Creates a record of a user subscription.",
)
def create_user_subscription(request, subscription: Subscription):
    sub = UserSubscription.objects.create(
        user=request.user,
        subscription=subscription.subscription,
    )
    return 201, map_sub(sub)


@router.delete(
    "/{sub_id}",
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    description="Deletes a user subscription record.",
)
def delete_user_subscription(request, sub_id: int, code: str = None):
    sub = UserSubscription.objects.filter(id=sub_id).first()
    if not sub:
        return 404, ErrorResponse(detail=f"Subscription {sub_id} not found")
    if (code != settings.SHARED_SECRET) and (sub.user != request.user):
        return 403, ErrorResponse(
            detail="Not permitted to delete this subscription"
        )
    sub.delete()
    return 204, None
