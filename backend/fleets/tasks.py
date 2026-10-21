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
