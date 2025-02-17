import logging
from typing import List

from ninja import Router
from pydantic import BaseModel
from django.conf import settings

from app.errors import ErrorResponse
from authentication import AuthBearer

from .models import UserSubscription

router = Router(tags=["Subscriptions"])

log = logging.getLogger(__name__)


class Subscription(BaseModel):
    id: int = None
    user_id: int = None
    subscription: str


class NewSubscription(BaseModel):
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
def get_subscriptions(request, user_id: int = None, authcode: str = None):
    query = UserSubscription.objects.all()
    if user_id:
        query = query.filter(user__id=user_id)
    elif authcode != settings.SHARED_SECRET:
        return 403, ErrorResponse(detail="Not authorised for all users")
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
def create_user_subscription(request, subscription: NewSubscription):
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
    if (authcode != settings.SHARED_SECRET) and (sub.user != request.user):
        return 403, ErrorResponse(
            detail="Not permitted to delete this subscription"
        )
    sub.delete()
    return 204, None
