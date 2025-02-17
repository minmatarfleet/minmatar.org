import logging
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from app.settings import SHARED_SECRET
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
    description="Returns subscriptions details.",
)
def get_subscriptions(request, user_id: int = None):
    query = UserSubscription.objects.all()
    if user_id:
        query = query.filter(user__id=user_id)
    response = []
    for sub in query:
        response.append(map_sub(sub))
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
def delete_user_subscription(request, sub_id: int, authcode: str = None):
    sub = UserSubscription.objects.filter(id=sub_id).first()
    if not sub:
        return 404, ErrorResponse(detail=f"Subscription {sub_id} not found")
    if (authcode != SHARED_SECRET) and (sub.user != request.user):
        return 403, ErrorResponse(
            detail="Not permitted to delete this subscription"
        )
    sub.delete()
    return 204, None
