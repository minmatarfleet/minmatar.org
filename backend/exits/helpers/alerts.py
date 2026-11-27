"""Alerts in the recruiter-only channel about applicants with history (design 06).

Never in the application's own thread (the applicant is in it). The message
says only that history exists: no reasons, notes or CEO names, which live on
the recruiter-gated application page.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from applications.discord import _recruiter_role_mention, application_url
from applications.models import EveCorporationApplication
from discord.client import DiscordClient
from discord.forum_threads import flagged_channel_row
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.history import active_flags_for, history_for
from exits.models import REASON_KICKED_OTHER, RecruiterAlert

logger = logging.getLogger(__name__)

discord = DiscordClient()


def alert_reason(application) -> str | None:
    if active_flags_for(application.user, []):
        return RecruiterAlert.REASON_FLAG
    if any(
        entry.reason == REASON_KICKED_OTHER
        for entry in history_for(application.user, [])
    ):
        return RecruiterAlert.REASON_KICKED_OTHER
    return None


def _applicant_name(application) -> str:
    character = user_primary_character(application.user) or (
        EveCharacter.objects.filter(user=application.user).first()
    )
    return character.character_name if character else application.user.username


def alert_message(application, corporation, reason) -> str:
    lines = [
        _recruiter_role_mention(corporation),
        f"⚠ {_applicant_name(application)}, applying to {corporation.name}, "
        "has alliance history",
    ]
    if reason == RecruiterAlert.REASON_FLAG:
        flag = active_flags_for(application.user, [])[0]
        lines.append(
            f"Includes a can't-rejoin flag from {flag.corporation.name}."
        )
    lines.append(f"Open the application: {application_url(application)}")
    lines.append(
        "Details are on the application page. The applicant can't see this channel."
    )
    return "\n".join(line for line in lines if line)


def _already_alerted(application, reason) -> bool:
    sent = RecruiterAlert.objects.filter(
        application=application, corporation_id=application.corporation_id
    ).values_list("reason", flat=True)
    if reason == RecruiterAlert.REASON_FLAG:
        return RecruiterAlert.REASON_FLAG in sent
    # "Kicked for another reason" only when nothing was sent yet.
    return bool(sent)


def send_alert(application_id: int) -> bool:
    """Post the alert for this application, once. True when one was sent."""
    application = (
        EveCorporationApplication.objects.select_related("user")
        .filter(pk=application_id, status="pending")
        .first()
    )
    if application is None:
        return False
    reason = alert_reason(application)
    if reason is None or _already_alerted(application, reason):
        return False
    corporation = EveCorporation.objects.filter(
        corporation_id=application.corporation_id
    ).first()
    if corporation is None:
        return False
    channel = flagged_channel_row("receive_recruiter_alerts")
    if channel is None:
        logger.info(
            "No recruiter alerts channel: not alerting on application %s (%s)",
            application.pk,
            reason,
        )
        return False
    try:
        with transaction.atomic():
            alert = RecruiterAlert.objects.create(
                application=application,
                corporation_id=application.corporation_id,
                reason=reason,
                sent_at=timezone.now(),
            )
    except IntegrityError:
        return False
    response = discord.create_message(
        channel_id=channel[0],
        message=alert_message(application, corporation, reason),
    )
    try:
        alert.message_id = int(response.json()["id"])
        alert.save(update_fields=["message_id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        logger.warning("No message id for recruiter alert %s", alert.pk)
    return True


def open_applications_for(user, character_ids) -> list[int]:
    """Pending applications of this pilot (by account), for a new flag."""
    if user is None:
        user_ids = set(
            EveCharacter.objects.filter(
                character_id__in=character_ids, user__isnull=False
            ).values_list("user_id", flat=True)
        )
    else:
        user_ids = {user.pk}
    return list(
        EveCorporationApplication.objects.filter(
            user_id__in=user_ids, status="pending"
        ).values_list("pk", flat=True)
    )
