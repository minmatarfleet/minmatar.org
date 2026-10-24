import logging

from django.utils import timezone
from django.conf import settings

from app.celery import app
from app.links import (
    new_player_fleet_guide_url,
    site_url,
    upcoming_fleets_url,
)
from discord.client import DiscordClient
from discord.outbox import on_commit_enqueue
from fleets.helpers.active_clones import (
    POLL_SPREAD_SECONDS,
    members_to_poll,
    poll_fleet_member_implants as poll_member_implants_impl,
)
from fleets.helpers.npsi_ingest import poll_npsi_sources
from fleets.models import CAMPAIGN_FLEET_TYPES, EveFleet, EveFleetInstance
from tribes.helpers.publishing import group_page_path

discord_client = DiscordClient()
logger = logging.getLogger(__name__)

FLEET_SCHEDULE_CHANNEL_ID = settings.DISCORD_FLEET_SCHEDULE_CHANNEL_ID


def get_fleet_emoji(fleet_type):
    """Get the emoji string in format <:name:id> for a fleet type"""
    logger.info("Getting fleet emoji for %s", fleet_type)
    if fleet_type in settings.DISCORD_FLEET_EMOJIS:
        return f"<:{settings.DISCORD_FLEET_EMOJIS[fleet_type]['name']}:{settings.DISCORD_FLEET_EMOJIS[fleet_type]['id']}>"
    return ""


@app.task(expires=30, exclusive=5 * 60)
def update_fleet_instances():
    """
    Update fleet instances
    """
    active_fleet_instances = EveFleetInstance.objects.filter(end_time=None)
    logger.debug(
        "Updating status of %s fleets", active_fleet_instances.count()
    )
    for fleet_instance in active_fleet_instances:
        logger.info("Updating fleet instance %s", fleet_instance.id)
        fleet_instance.update_is_registered_status()
        fleet_instance.update_fleet_members()


# Saves within a couple of seconds share one refresh; see
# queue_fleet_schedule_refresh.
SCHEDULE_REFRESH_DELAY_SECONDS = 2


@app.task()
def update_fleet_schedule():
    """
    Updates fleet schedule message to display all upcoming fleets
    Message format: <fleet type> | <eve time> | <local discord timestamp> | <fleet commander name>
    """
    fleets = (
        EveFleet.objects.filter(start_time__gte=timezone.now())
        .exclude(status="cancelled")
        # A standing fleet is always up and a gang forms on the spot;
        # neither belongs on a schedule of upcoming fleets.
        .exclude(type__in=CAMPAIGN_FLEET_TYPES)
        # Private fleets are never scheduled, even once declassified.
        .exclude(invite_only=True)
        .order_by("start_time")
        .select_related(
            "location", "audience", "created_by", "host_group__tribe"
        )
    )

    # Group fleets by location
    fleets_by_location = {}
    tribe_fleets = []
    for fleet in fleets:
        if fleet.host_group_id:
            if fleet.open_to_alliance and fleet.on_schedule:
                tribe_fleets.append(fleet)
            continue
        if fleet.audience and fleet.audience.add_to_schedule:
            location_name = (
                fleet.formup_location.location_name
                if fleet.formup_location
                else "No Location"
            )
            if location_name not in fleets_by_location:
                fleets_by_location[location_name] = []
            fleets_by_location[location_name].append(fleet)

    message = "## Fleet Schedule\n"

    if not fleets_by_location:
        message += "- No upcoming fleets, go touch grass you nerd"
    else:
        # Sort locations alphabetically
        for location_name in sorted(fleets_by_location.keys()):
            message += f"\n**{location_name}**\n"
            for fleet in fleets_by_location[location_name]:
                fleet_emoji = get_fleet_emoji(fleet.type)
                fc_name = (
                    fleet.fleet_commander.character_name
                    if fleet.fleet_commander
                    else ""
                )
                # pylint: disable=inconsistent-quotes
                message += f"- {fleet_emoji} {fleet.start_time.strftime('%Y-%m-%d %H:%M')} EVE (<t:{int(fleet.start_time.timestamp())}>) {fc_name}\n"
    message += tribe_fleets_section(message, tribe_fleets)
    payload = {
        "content": message,
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "style": 5,
                        "label": "View Fleet Board",
                        "url": upcoming_fleets_url(),
                        "disabled": False,
                        "type": 2,
                    },
                    {
                        "style": 5,
                        "label": "New Player Instructions",
                        "url": new_player_fleet_guide_url(),
                        "disabled": False,
                        "type": 2,
                    },
                ],
            }
        ],
    }

    # Delete all messages in the channel
    messages = discord_client.get_messages(FLEET_SCHEDULE_CHANNEL_ID)
    for msg in messages:
        try:
            discord_client.delete_message(FLEET_SCHEDULE_CHANNEL_ID, msg["id"])
        except Exception as e:
            logger.warning("Failed to delete message %s: %s", msg["id"], e)

    # Post new message
    discord_client.create_message(FLEET_SCHEDULE_CHANNEL_ID, payload=payload)


DISCORD_MESSAGE_LIMIT = 2000
TRIBE_FLEETS_HEADING = "### Tribe fleets\n"
TRIBE_FLEETS_FOOTER = (
    "-# Open to the alliance: message the FC or apply on the group's page."
)


def _tribe_fleet_line(fleet) -> str:
    group = fleet.host_group
    fc_name = (
        fleet.fleet_commander.character_name if fleet.fleet_commander else ""
    )
    group_url = site_url(group_page_path(group))
    when = fleet.start_time.strftime("%Y-%m-%d %H:%M")
    line = (
        f"- {get_fleet_emoji(fleet.type)} {when} EVE "
        f"(<t:{int(fleet.start_time.timestamp())}>) {fc_name} · "
        f"[{group.name}](<{group_url}>) ({group.tribe.name})"
    )
    title = fleet.objective or (fleet.doctrine.name if fleet.doctrine else "")
    if title:
        line += f" · {title}"
    return line + "\n"


def tribe_fleets_section(message: str, tribe_fleets: list) -> str:
    """The "### Tribe fleets" part of the #schedule message.

    Empty when no open group fleet asked to be on the schedule, so the
    message is unchanged. Lines that would take the message past Discord's
    2000 characters become one "…and N more" line.
    """
    if not tribe_fleets:
        return ""
    head = ("" if message.endswith("\n") else "\n") + "\n"
    head += TRIBE_FLEETS_HEADING
    budget = DISCORD_MESSAGE_LIMIT - len(message) - len(head)
    budget -= len(TRIBE_FLEETS_FOOTER)
    lines = [_tribe_fleet_line(fleet) for fleet in tribe_fleets]
    shown = []
    for index, line in enumerate(lines):
        left = len(lines) - index - 1
        more = f"…and {left} more\n" if left else ""
        if len("".join(shown)) + len(line) + len(more) > budget:
            break
        shown.append(line)
    hidden = len(lines) - len(shown)
    body = "".join(shown)
    if hidden:
        body += f"…and {hidden} more\n"
    return head + body + TRIBE_FLEETS_FOOTER


def queue_fleet_schedule_refresh() -> None:
    """Refresh the Discord schedule message from a worker, after commit.

    The refresh deletes and re-posts the channel's messages, so it must not
    run inside a web request. One queued refresh covers every save made
    before it starts: AppTask drops duplicates while one is waiting and
    unlocks when a worker starts it, so a save during a run queues another.
    """
    on_commit_enqueue(
        update_fleet_schedule,
        context="fleet schedule refresh",
        countdown=SCHEDULE_REFRESH_DELAY_SECONDS,
    )


@app.task(expires=60 * 60)
def save_copied_fleet_fits(fleet_id: int):
    """Save a copied fleet's custom fits and refits in-game under its FC."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.copy_fleet import save_copied_fits

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None:
        return 0
    return save_copied_fits(fleet)


def queue_save_copied_fleet_fits(fleet: EveFleet) -> None:
    """Queue save_copied_fleet_fits after commit, when there is a fit to save."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.copy_fleet import fits_to_save

    if fits_to_save(fleet):
        on_commit_enqueue(
            save_copied_fleet_fits,
            (fleet.id,),
            context=f"saving copied fits for fleet {fleet.id}",
        )


@app.task(exclusive=30 * 60)
def poll_active_fleet_implants():
    """Queue implant polls for active fleet members within the 45-minute window."""
    members = members_to_poll()
    if not members:
        return 0

    member_count = len(members)
    for index, member in enumerate(members):
        countdown = int(index * POLL_SPREAD_SECONDS / member_count)
        poll_fleet_member_implants.apply_async(
            args=[member.id],
            countdown=countdown,
        )

    logger.info("Queued implant polls for %s fleet member(s)", member_count)
    return member_count


@app.task()
def poll_fleet_member_implants(member_id: int):
    """Poll implants for one fleet member."""
    return poll_member_implants_impl(member_id)


@app.task(exclusive=10 * 60)
def poll_npsi_events():
    """Fetch NPSI calendar feeds and DM FCs to confirm schedule posts."""
    stats = poll_npsi_sources()
    logger.info("NPSI poll %s", stats)
    return stats


@app.task()
def nudge_missing_signups(fleet_id: int):
    """DM signed-up pilots who are not in the live fleet yet."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.missing_signups import send_missing_signup_nudges

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet:
        send_missing_signup_nudges(fleet)


@app.task(expires=30, exclusive=5 * 60)
def rebuild_fight_timelines():
    """Rebuild every live or unsettled fleet's fight timeline.

    Each fleet rebuilds from scratch; one that fails is logged and the rest
    carry on. Sweeps and settling need zKill and eve-kill, so they run as
    their own tasks.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.fights import timeline as fights

    now = timezone.now()
    for fleet in EveFleet.objects.filter(id__in=fights.due_fleet_ids(now)):
        try:
            timeline = fights.rebuild(fleet, now=now)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Fight timeline rebuild failed for %s", fleet.id)
            continue
        step = fights.next_step(fleet, timeline, now)
        if step == "sweep":
            sweep_fight_killmails.delay(fleet.id)
        elif step == "settle":
            settle_fight_timeline.delay(fleet.id)


@app.task(expires=60, cooldown=10)
def rebuild_fight_timeline(fleet_id: int):
    """Build one fleet's timeline on demand, e.g. a fleet from before it existed."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.fights import timeline as fights

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet:
        fights.rebuild(fleet)


@app.task(expires=15 * 60, exclusive=15 * 60)
def sweep_fight_killmails(fleet_id: int):
    """Fill in killmails the live feed missed, from zKill, then rebuild."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.fights import timeline as fights

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return None
    stats = fights.sweep(fleet)
    fights.rebuild(fleet)
    logger.info("Fight timeline sweep for fleet %s: %s", fleet_id, stats)
    return stats


@app.task(expires=15 * 60, exclusive=15 * 60)
def settle_fight_timeline(fleet_id: int):
    """Last rebuild two hours after the fleet, plus eve-kill battle links,
    then mail the FC the fleet's numbers."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.close_mail import send_fleet_report
    from fleets.helpers.fights import timeline as fights

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet:
        send_fleet_report(fleet, fights.settle(fleet))


# --- Private fleets (docs/fleets/private-fleets.md) ------------------------

# Seconds between invite DMs. Opening many new DM channels at once trips
# Discord's anti-spam (error 40003), so a wave goes out at about one a second.
INVITE_DM_SPACING_SECONDS = 1.0


def _pace():
    # pylint: disable=import-outside-toplevel
    import time

    if not getattr(settings, "TESTING", False):
        time.sleep(INVITE_DM_SPACING_SECONDS)


def _send_invite_dm(invite, *, reminder: bool = False) -> bool:
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleet_discord import send_invite_dm

    return send_invite_dm(discord_client, invite, reminder=reminder)


@app.task(exclusive=30 * 60)
def send_fleet_invite_wave(wave_id: int):
    """Send a wave's invite DMs, about one a second. Safe to run twice:
    invites already tried are skipped."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInvite, EveFleetInviteWave

    wave = (
        EveFleetInviteWave.objects.select_related("eve_fleet")
        .filter(id=wave_id)
        .first()
    )
    if wave is None or wave.finished_at:
        return
    invites = (
        EveFleetInvite.objects.filter(wave=wave, dm_delivered__isnull=True)
        .select_related(
            "wave",
            "eve_fleet__doctrine",
            "eve_fleet__location",
            "eve_fleet__created_by",
        )
        .order_by("id")
    )
    for index, invite in enumerate(invites):
        if index:
            _pace()
        _send_invite_dm(invite)
    wave.finished_at = timezone.now()
    wave.save(update_fields=["finished_at"])


@app.task(exclusive=30 * 60)
def send_fleet_invite_reminders(fleet_id: int, invite_ids: list[int]):
    """Re-ping no answers: one more invite DM each, paced like a wave."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInvite

    invites = EveFleetInvite.objects.filter(
        eve_fleet_id=fleet_id,
        id__in=invite_ids,
        answer=EveFleetInvite.ANSWER_PENDING,
    ).select_related("wave", "eve_fleet__doctrine", "eve_fleet__location")
    for index, invite in enumerate(invites):
        if index:
            _pace()
        _send_invite_dm(invite, reminder=True)


def _edit_invite_dm(invite) -> None:
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleet_discord import answered_payload

    if not invite.dm_channel_id or not invite.dm_message_id:
        return
    try:
        discord_client.update_message(
            invite.dm_channel_id,
            invite.dm_message_id,
            payload=answered_payload(invite),
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not edit private fleet invite DM %s",
            invite.id,
            exc_info=True,
        )


def _thread_add(fleet, user_id: int) -> bool:
    # pylint: disable=import-outside-toplevel
    from discord.models import DiscordUser

    discord_user = DiscordUser.objects.filter(user_id=user_id).first()
    if discord_user is None or not fleet.discord_thread_id:
        return False
    try:
        discord_client.add_thread_member(
            fleet.discord_thread_id, discord_user.id
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not add user %s to fleet %s thread",
            user_id,
            fleet.id,
            exc_info=True,
        )
        return False
    return True


def _thread_remove(fleet, user_id: int) -> None:
    # pylint: disable=import-outside-toplevel
    from discord.models import DiscordUser

    discord_user = DiscordUser.objects.filter(user_id=user_id).first()
    if discord_user is None or not fleet.discord_thread_id:
        return
    try:
        discord_client.remove_thread_member(
            fleet.discord_thread_id, discord_user.id
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not remove user %s from fleet %s thread",
            user_id,
            fleet.id,
            exc_info=True,
        )


@app.task()
def sync_private_fleet_invite(invite_id: int):
    """After an answer: edit the DM, add to or remove from the thread, and
    refresh the thread's pinned summary."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_visibility import sees_every_private_fleet
    from fleets.models import EveFleetInvite

    invite = (
        EveFleetInvite.objects.select_related(
            "eve_fleet__audience", "eve_fleet__location", "wave", "user"
        )
        .filter(id=invite_id)
        .first()
    )
    if invite is None:
        return
    fleet = invite.eve_fleet
    _edit_invite_dm(invite)
    if invite.answer == EveFleetInvite.ANSWER_IN and not invite.in_thread:
        if _thread_add(fleet, invite.user_id):
            invite.in_thread = True
            invite.save(update_fields=["in_thread"])
    elif invite.answer != EveFleetInvite.ANSWER_IN and invite.in_thread:
        # Strategic FCs stay in the thread whatever they answer.
        if not sees_every_private_fleet(invite.user):
            _thread_remove(fleet, invite.user_id)
        invite.in_thread = False
        invite.save(update_fields=["in_thread"])
    refresh_private_fleet_summary.delay(fleet.id)


@app.task(exclusive=10 * 60)
def ensure_private_fleet_thread(fleet_id: int):
    """Open the fleet's private thread with the FC and every Strategic FC,
    and pin the summary. Safe to run twice."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleet_discord import (
        strategic_fc_user_ids,
        summary_payload,
        thread_name,
        thread_parent_channel_id,
    )

    fleet = (
        EveFleet.objects.select_related("audience", "location", "created_by")
        .filter(id=fleet_id, invite_only=True)
        .first()
    )
    if fleet is None:
        return
    if not fleet.discord_thread_id:
        parent = thread_parent_channel_id(fleet)
        if not parent:
            logger.warning("Private fleet %s has no thread channel", fleet_id)
            return
        thread = discord_client.create_private_thread(
            parent, thread_name(fleet)
        )
        fleet.discord_thread_id = int(thread["id"])
        fleet.save(update_fields=["discord_thread_id"])
    members = strategic_fc_user_ids()
    if fleet.created_by_id:
        members.add(fleet.created_by_id)
    for index, user_id in enumerate(sorted(members)):
        if index:
            _pace()
        _thread_add(fleet, user_id)
    if not fleet.discord_summary_message_id:
        message = discord_client.create_message(
            fleet.discord_thread_id, payload=summary_payload(fleet)
        ).json()
        fleet.discord_summary_message_id = int(message["id"])
        fleet.save(update_fields=["discord_summary_message_id"])
        try:
            discord_client.pin_message(fleet.discord_thread_id, message["id"])
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Could not pin fleet %s summary", fleet_id, exc_info=True
            )


@app.task()
def refresh_private_fleet_summary(fleet_id: int):
    """Edit the pinned summary in the fleet's thread."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleet_discord import summary_payload

    fleet = (
        EveFleet.objects.select_related("location", "created_by")
        .filter(id=fleet_id, invite_only=True)
        .first()
    )
    if (
        fleet is None
        or not fleet.discord_thread_id
        or not fleet.discord_summary_message_id
    ):
        return
    try:
        discord_client.update_message(
            fleet.discord_thread_id,
            fleet.discord_summary_message_id,
            payload=summary_payload(fleet),
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not edit fleet %s summary", fleet_id, exc_info=True
        )


@app.task()
def post_private_fleet_start_ping(fleet_id: int):
    """The start ping, in the private thread, with @everyone. Refuses to
    post anywhere that isn't a private thread: a wrong id would ping the
    whole parent channel."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleet_discord import (
        is_private_thread,
        thread_start_ping_payload,
    )

    fleet = EveFleet.objects.filter(id=fleet_id, invite_only=True).first()
    if fleet is None or not fleet.discord_thread_id:
        return
    if not is_private_thread(discord_client, fleet.discord_thread_id):
        logger.error(
            "Fleet %s thread %s isn't a private thread; start ping not sent",
            fleet_id,
            fleet.discord_thread_id,
        )
        return
    ping = fleet.start_ping()
    if ping is None:
        return
    discord_client.create_message(
        fleet.discord_thread_id,
        payload=thread_start_ping_payload(ping.payload),
    )


@app.task(exclusive=30 * 60)
def update_private_fleet_dms(fleet_id: int):
    """Edit every invite DM after the fleet starts, ends or is cancelled."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInvite

    invites = EveFleetInvite.objects.filter(
        eve_fleet_id=fleet_id, dm_message_id__isnull=False
    ).select_related("eve_fleet", "wave")
    for index, invite in enumerate(invites):
        if index:
            _pace()
        _edit_invite_dm(invite)


@app.task()
def close_private_fleet_thread(fleet_id: int):
    """Lock and archive the thread once the fleet is over."""
    fleet = EveFleet.objects.filter(id=fleet_id, invite_only=True).first()
    if fleet is None or not fleet.discord_thread_id:
        return
    try:
        discord_client.close_thread(fleet.discord_thread_id)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Could not close fleet %s thread", fleet_id, exc_info=True
        )
