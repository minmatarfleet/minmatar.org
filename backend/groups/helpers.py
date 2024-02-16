import logging
from typing import List

from django.contrib.auth.models import Group, User

from groups.models import RequestableGroup

from .models import GroupRequest
from .schemas import GroupSchema, GroupStatus

logger = logging.getLogger(__name__)


def get_group(group_id: int, user_id: int) -> GroupSchema:
    """Fetches a group with a status based on the supplied user"""
    if not Group.objects.filter(id=group_id).exists():
        return None
    if not User.objects.filter(id=user_id).exists():
        return None
    user = User.objects.get(id=user_id)
    group = Group.objects.get(id=group_id)
    description = None
    image_url = None
    if hasattr(group, "requestablegroup"):
        description = group.requestablegroup.description
        image_url = group.requestablegroup.image_url
    elif hasattr(group, "autogroup"):
        description = group.autogroup.description
        image_url = group.autogroup.image_url
    status = None
    if RequestableGroup.objects.filter(group=group).exists():
        status = GroupStatus.AVAILABLE.value
    if GroupRequest.objects.filter(
        user=user, approved=None, group=group
    ).exists():
        status = GroupStatus.REQUESTED.value
    if Group.objects.filter(user=user, id=group.id).exists():
        status = GroupStatus.CONFIRMED.value

    payload = {
        "id": group.id,
        "name": group.name,
        "description": description,
        "image_url": image_url,
        "status": status,
    }

    return GroupSchema(**payload)


def get_requestable_groups_for_user(user) -> List[RequestableGroup]:
    groups = RequestableGroup.objects.all()
    available_groups = []
    # filter out availalbe groups if user is missing group
    for group in groups:
        available = True
        logger.info(f"Checking group {group.group.name}")
        if group.required_groups:
            logger.info(f"Group {group.group.name} has required groups")
            for required_group in group.required_groups.all():
                logger.info(
                    f"Checking for required group {required_group.name}"
                )
                logger.info(f"User groups: {user.groups.all()}")
                if required_group not in user.groups.all():
                    logger.info(
                        f"User is missing required group {required_group.name}"
                    )
                    available = False
        if available:
            logger.info(f"Group {group.group.name} is available")
            available_groups.append(group)
    logger.info(f"Available groups: {available_groups}")
    return available_groups


def get_requestable_group_ids_for_user(user):
    groups = get_requestable_groups_for_user(user)
    response = [group.group.id for group in groups]
    logger.info(f"Requestable group ids for user {user}: {response}")
    return response
