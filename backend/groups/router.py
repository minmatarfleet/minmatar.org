import logging
from enum import Enum
from typing import List, Optional

from django.contrib.auth.models import Group, User
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from groups.models import GroupRequest, RequestableGroup

from .helpers import (
    get_requestable_group_ids_for_user,
    get_requestable_groups_for_user,
)

logger = logging.getLogger(__name__)
router = Router(tags=["Groups"])


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]


class GroupStatus(str, Enum):
    AVAILABLE = "available"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"


class AvailableGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]
    status: str


# get my groups
@router.get(
    "",
    response=List[GroupResponse],
    auth=AuthBearer(),
    description="Get the groups of the current user",
)
def get_groups(request):
    groups = Group.objects.filter(user__id=request.user.id)
    response = []
    for group in groups:
        description = None
        image_url = None
        if hasattr(group, "requestablegroup"):
            description = group.requestablegroup.description
            image_url = group.requestablegroup.image_url
        elif hasattr(group, "autogroup"):
            description = group.autogroup.description
            image_url = group.autogroup.image_url
        response.append(
            {
                "id": group.id,
                "name": group.name,
                "description": description,
                "image_url": image_url,
            }
        )
    return response


@router.get(
    "/available", response=List[AvailableGroupResponse], auth=AuthBearer()
)
def get_available_groups(request):
    available_groups = get_requestable_groups_for_user(request.user)
    response = []

    for group in available_groups:
        status = GroupStatus.AVAILABLE
        if GroupRequest.objects.filter(
            user=request.user, approved=None, group=group.group
        ).exists():
            status = GroupStatus.REQUESTED
        if Group.objects.filter(user=request.user, id=group.group.id).exists():
            status = GroupStatus.CONFIRMED
        response.append(
            {
                "id": group.group.id,
                "name": group.group.name,
                "description": group.description,
                "image_url": group.image_url,
                "status": status,
            }
        )
    return response


class GroupRequestResponse(BaseModel):
    id: int
    user: int
    group: int
    approved: Optional[bool]
    approved_by: Optional[int]
    approved_at: Optional[str]


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/{group_id}/requests",
    auth=AuthBearer(),
    response={
        200: List[GroupRequestResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_group_requests(request, group_id: int):
    if not Group.objects.filter(id=group_id).exists():
        return 404, {"detail": "Group does not exist."}
    if not RequestableGroup.objects.filter(group__id=group_id).exists():
        return 404, {"detail": "Group is not requestable."}

    requestable_group_settings = RequestableGroup.objects.get(
        group__id=group_id
    )
    group = Group.objects.get(id=group_id)
    if (
        request.user not in requestable_group_settings.group_managers.all()
        and not request.user.has_perm("groups.view_grouprequest")
    ):
        return 403, {
            "detail": "You do not have permission to view requests for this group."
        }
    requests = GroupRequest.objects.filter(group=group)
    response = []
    for group_request in requests:
        response.append(
            {
                "id": group_request.id,
                "user": group_request.user.id,
                "group": group_request.group.id,
                "approved": group_request.approved,
                "approved_by": (
                    group_request.approved_by.id
                    if group_request.approved_by
                    else None
                ),
                "approved_at": group_request.approved_at,
            }
        )
    return response


@router.post(
    "/{group_id}/requests",
    auth=AuthBearer(),
    response={201: GroupRequestResponse, 400: ErrorResponse},
)
def create_group_request(request, group_id: int):
    group = Group.objects.get(id=group_id)
    if GroupRequest.objects.filter(user=request.user, group=group).exists():
        return 400, {"detail": "You have already requested this group."}
    if not RequestableGroup.objects.filter(group=group).exists():
        return 400, {"detail": "Group is not requestable."}
    requestable_group_ids = get_requestable_group_ids_for_user(request.user)
    if group_id not in requestable_group_ids:
        return 400, {
            "detail": "You do not have permission to request this group."
        }
    group_request = GroupRequest.objects.create(user=request.user, group=group)
    return 201, {
        "id": group_request.id,
        "user": group_request.user.id,
        "group": group_request.group.id,
        "approved": group_request.approved,
        "approved_by": (
            group_request.approved_by.id if group_request.approved_by else None
        ),
        "approved_at": group_request.approved_at,
    }


@router.post(
    "/{group_id}/requests/{request_id}/approve",
    response={
        200: GroupRequestResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
)
def approve_group_request(request, group_id: int, request_id: int):
    if not Group.objects.filter(id=group_id).exists():
        return 404, {"detail": "Group does not exist."}
    group = Group.objects.get(id=group_id)
    if not RequestableGroup.objects.filter(group=group).exists():
        return 404, {"detail": "Group is not requestable."}
    requestable_group_settings = RequestableGroup.objects.get(group=group)
    if not GroupRequest.objects.filter(id=request_id, group=group).exists():
        return 404, {"detail": "Request does not exist."}
    group_request = GroupRequest.objects.get(id=request_id, group=group)
    if (
        request.user not in requestable_group_settings.group_managers.all()
        and not request.user.has_perm("groups.manage_grouprequest")
    ):
        return 403, {
            "detail": "You do not have permission to approve requests for this group."
        }

    if group_request.approved:
        return 400, {"detail": "Request has already been approved."}
    group_request.approved = True
    group_request.approved_by = request.user
    group_request.save()
    # add user to group
    group.user_set.add(group_request.user)
    return 200, {
        "id": group_request.id,
        "user": group_request.user.id,
        "group": group_request.group.id,
        "approved": group_request.approved,
        "approved_by": (
            group_request.approved_by.id if group_request.approved_by else None
        ),
        "approved_at": group_request.approved_at,
    }


@router.post(
    "/{group_id}/requests/{request_id}/deny",
    response={
        200: GroupRequestResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
)
def deny_group_request(request, group_id: int, request_id: int):
    if not Group.objects.filter(id=group_id).exists():
        return 404, {"detail": "Group does not exist."}
    group = Group.objects.get(id=group_id)
    if not RequestableGroup.objects.filter(group=group).exists():
        return 404, {"detail": "Group is not requestable."}
    requestable_group_settings = RequestableGroup.objects.get(group=group)
    if not GroupRequest.objects.filter(id=request_id, group=group).exists():
        return 404, {"detail": "Request does not exist."}
    group_request = GroupRequest.objects.get(id=request_id, group=group)
    if (
        request.user not in requestable_group_settings.group_managers.all()
        and not request.user.has_perm("groups.manage_grouprequest")
    ):
        return 403, {
            "detail": "You do not have permission to approve requests for this group."
        }
    if group_request.approved:
        return 400, {"detail": "Request has already been approved."}
    group_request.approved = False
    group_request.approved_by = request.user
    group_request.save()
    return 200, {
        "id": group_request.id,
        "user": group_request.user.id,
        "group": group_request.group.id,
        "approved": group_request.approved,
        "approved_by": (
            group_request.approved_by.id if group_request.approved_by else None
        ),
        "approved_at": group_request.approved_at,
    }


@router.get(
    "/{group_id}/users",
    response={200: list, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
)
def get_group_users(request, group_id: int):
    if not Group.objects.filter(id=group_id).exists():
        return 404, {"detail": "Group does not exist."}
    group = Group.objects.get(id=group_id)
    if not RequestableGroup.objects.filter(group=group).exists():
        return 404, {"detail": "Group is not requestable."}
    requestable_group_settings = RequestableGroup.objects.get(group=group)
    if (
        request.user not in requestable_group_settings.group_managers.all()
        and not request.user.has_perm("groups.manage_grouprequest")
    ):
        return 403, {
            "detail": "You do not have permission to approve requests for this group."
        }
    users = group.user_set.all()
    response = []
    for user in users:
        response.append(user.id)
    return response


@router.delete(
    "/{group_id}/users/{user_id}",
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
)
def remove_user_from_group(request, group_id: int, user_id: int):
    if not Group.objects.filter(id=group_id).exists():
        return 404, {"detail": "Group does not exist."}
    group = Group.objects.get(id=group_id)
    if not RequestableGroup.objects.filter(group=group).exists():
        return 404, {"detail": "Group is not requestable."}
    requestable_group_settings = RequestableGroup.objects.get(group=group)
    if (
        request.user not in requestable_group_settings.group_managers.all()
        and not request.user.has_perm("groups.manage_grouprequest")
    ):
        return 403, {
            "detail": "You do not have permission to approve requests for this group."
        }
    user = User.objects.get(id=user_id)
    group.user_set.remove(user)
    return 204, None
