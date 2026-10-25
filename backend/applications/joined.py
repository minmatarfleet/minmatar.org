"""Close pending applications once the applicant is in the corporation.

Recruiters often invite pilots in game and forget to press accept on the
website, which leaves the application open and skews the corporation's
public "days to accept". Joining the corporation is the acceptance.
"""

import logging

from django.db.models import OuterRef, Q, Subquery

from eveonline.models import EveCharacterCorporationHistory

from .models import EveCorporationApplication

logger = logging.getLogger(__name__)


def pending_applications_of_members():
    """Pending applications whose applicant has a character that joined the
    corporation after applying and is still in it, annotated with
    ``joined_at``, the first such join.

    A character already in the corporation when the application was made
    (an alt, or a member re-applying) does not count.
    """
    joins = (
        EveCharacterCorporationHistory.objects.filter(
            Q(character__user_id=OuterRef("user_id"))
            | Q(character__token__user_id=OuterRef("user_id")),
            character__esi_deleted=False,
            character__corporation_id=OuterRef("corporation_id"),
            corporation_id=OuterRef("corporation_id"),
            start_date__gte=OuterRef("created_at"),
        )
        .order_by("start_date")
        .values("start_date")[:1]
    )
    return (
        EveCorporationApplication.objects.filter(status="pending")
        .annotate(joined_at=Subquery(joins))
        .filter(joined_at__isnull=False)
        .select_related("user")
    )


def accept_applications_of_members() -> list[int]:
    """Accept every pending application whose applicant joined.

    updated_at is set to the join, not now: it is the acceptance time the
    corporation page averages, and a backlog closed today must not count as
    weeks of waiting. update(), not save(): the post_save signal would post
    the "apply in-game" notice, and these pilots are already in. The caller
    queues the joined notice instead. Returns the accepted application ids.
    """
    accepted = []
    for application in pending_applications_of_members():
        updated = EveCorporationApplication.objects.filter(
            pk=application.pk, status="pending"
        ).update(status="accepted", updated_at=application.joined_at)
        if not updated:
            continue
        accepted.append(application.pk)
        logger.info(
            "Application %s for %s accepted: applicant joined %s at %s",
            application.pk,
            application.user.username,
            application.corporation_id,
            application.joined_at,
        )
    return accepted
