"""Close pending applications once the applicant is in the corporation.

Recruiters often invite pilots in game and forget to press accept on the
website, which leaves the application open and skews the corporation's
public "days to accept". Joining the corporation is the acceptance.
"""

import logging

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from eveonline.models import EveCharacter

from .models import EveCorporationApplication

logger = logging.getLogger(__name__)


def pending_applications_of_members():
    """Pending applications whose applicant has a character in the
    corporation they applied to."""
    member_character = EveCharacter.objects.filter(
        Q(user_id=OuterRef("user_id")) | Q(token__user_id=OuterRef("user_id")),
        corporation_id=OuterRef("corporation_id"),
    )
    return EveCorporationApplication.objects.filter(
        Exists(member_character), status="pending"
    )


def accept_applications_of_members() -> list[int]:
    """Accept every pending application whose applicant already joined.

    update(), not save(): the post_save signal would post the "apply
    in-game" notice, and these pilots are already in. The caller queues the
    joined notice instead. Returns the accepted application ids.
    """
    accepted = []
    for application in pending_applications_of_members():
        updated = EveCorporationApplication.objects.filter(
            pk=application.pk, status="pending"
        ).update(status="accepted", updated_at=timezone.now())
        if not updated:
            continue
        accepted.append(application.pk)
        logger.info(
            "Application %s for %s accepted: applicant joined %s",
            application.pk,
            application.user.username,
            application.corporation_id,
        )
    return accepted
