"""Send exit and alliance move surveys once the CEO's hour to undo is over (design 07)."""

import logging
from datetime import datetime

from django.conf import settings
from django.db import transaction

from discord.models import DiscordUser
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter
from exits.helpers.grouping import group
from exits.models import (
    KIND_ALLIANCE_MOVE,
    KIND_EXIT,
    STATUS_CONFIRMED,
    Departure,
)
from notifications.channels import (
    ChannelSendError,
    EveMailRefused,
    _send_discord,
    send_eve_mail_to_character,
)
from surveys.definitions.exit import EXIT_DEFINITION_VERSION
from surveys.helpers import exit_tokens
from surveys.models import ExitSurveyInvite
from surveys.models.exit_invite import (
    CHANNEL_DISCORD_DM,
    CHANNEL_EVE_MAIL,
    STATUS_NOT_DELIVERED,
    STATUS_SENT,
)

logger = logging.getLogger(__name__)

DEFINITION_FOR_KIND = {KIND_EXIT: "exit", KIND_ALLIANCE_MOVE: "alliance_move"}


def _already_surveyed(departure: Departure) -> bool:
    """One survey per person, ever: per account when known, else per character."""
    if departure.user_id:
        character_ids = EveCharacter.objects.filter(
            user_id=departure.user_id
        ).values_list("character_id", flat=True)
        return (
            ExitSurveyInvite.objects.filter(user_id=departure.user_id).exists()
            or ExitSurveyInvite.objects.filter(
                character_id__in=list(character_ids) + [departure.character_id]
            ).exists()
        )
    return ExitSurveyInvite.objects.filter(
        character_id=departure.character_id
    ).exists()


def _target(members: list[Departure]) -> Departure:
    """The account's main if it left in this group, else the first to leave."""
    lead = members[0]
    if lead.user_id:
        main = user_primary_character(lead.user)
        for departure in members:
            if main and departure.character_id == main.character_id:
                return departure
    return min(members, key=lambda d: (d.first_missing_at, d.pk))


def _sender_name() -> str:
    character_id = int(
        getattr(settings, "NOTIFICATIONS_EVE_MAIL_CHARACTER_ID", 0) or 0
    )
    name = (
        EveCharacter.objects.filter(character_id=character_id)
        .values_list("character_name", flat=True)
        .first()
    )
    return name or "the Alliance Executor"


def survey_texts(departure: Departure, url: str) -> tuple[str, str, str]:
    """Subject, Eve mail body (HTML) and Discord text, as written in design 07."""
    pilot = (
        EveCharacter.objects.filter(character_id=departure.character_id)
        .values_list("character_name", flat=True)
        .first()
        or "pilot"
    )
    corporation = departure.corporation.name
    left_on = (
        f"{departure.first_missing_at.day} {departure.first_missing_at:%b}"
    )
    sender = _sender_name()
    subject = f"You left {corporation}. How was it?"
    first_name = pilot.split()[0]
    lines = [
        f"o7 {first_name},",
        f"You left {corporation} on {left_on}. Fair winds wherever you fly next.",
        "We'd like to know how your time there went, good or bad. It takes "
        "about three minutes, and only I read the answers: your old CEO and "
        "directors never see them.",
    ]
    mail = "<br><br>".join(lines) + (
        f'<br><br><a href="{url}">Answer the survey</a> '
        "(no login needed, open for 30 days)"
        f"<br><br>Thanks,<br>{sender}, Minmatar Fleet Alliance"
    )
    discord = "\n\n".join(lines) + (
        f"\n\nAnswer the survey (no login needed, open for 30 days): {url}"
        f"\n\nThanks,\n{sender}, Minmatar Fleet Alliance"
    )
    return subject, mail, discord


def _deliver(invite: ExitSurveyInvite, departure: Departure) -> None:
    url = exit_tokens.survey_url(exit_tokens.mint(invite))
    subject, mail, discord = survey_texts(departure, url)
    try:
        send_eve_mail_to_character(departure.character_id, subject, mail)
        invite.channel = CHANNEL_EVE_MAIL
        invite.status = STATUS_SENT
    except EveMailRefused:
        user = departure.user
        if user and DiscordUser.objects.filter(user=user).exists():
            _send_discord(user, {"title": subject, "body": discord})
            invite.channel = CHANNEL_DISCORD_DM
            invite.status = STATUS_SENT
        else:
            invite.channel = ""
            invite.status = STATUS_NOT_DELIVERED
    invite.save(update_fields=["channel", "status"])


def _send_group(members: list[Departure], now: datetime) -> bool:
    target = _target(members)
    ids = [d.pk for d in members]
    if target.destination_corporation_id is None or _already_surveyed(target):
        Departure.objects.filter(pk__in=ids).update(survey_due_at=None)
        return False
    with transaction.atomic():
        invite = ExitSurveyInvite.objects.create(
            departure=target,
            character_id=target.character_id,
            user=target.user,
            definition_key=DEFINITION_FOR_KIND[target.kind],
            definition_version=EXIT_DEFINITION_VERSION,
            status=STATUS_SENT,
            sent_at=now,
            expires_at=now + exit_tokens.MAX_AGE,
        )
        # A retryable failure raises and rolls the invite back: next run.
        _deliver(invite, target)
        Departure.objects.filter(pk__in=ids).update(survey_due_at=None)
    return True


def send_due(now: datetime) -> int:
    due = list(
        Departure.objects.filter(
            status=STATUS_CONFIRMED,
            reason="left",
            survey_due_at__lte=now,
            survey_invite__isnull=True,
            kind__in=list(DEFINITION_FOR_KIND),
        ).select_related("corporation", "user")
    )
    sent = 0
    for members in group(due):
        try:
            sent += int(_send_group(members, now))
        except ChannelSendError as error:
            logger.warning(
                "Exit survey for departure %s not sent yet: %s",
                members[0].pk,
                error,
            )
    return sent
