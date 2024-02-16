import logging

from groups.models import RequestableGroup
from typing import List

logger = logging.getLogger(__name__)


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
