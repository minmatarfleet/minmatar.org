import logging

from django.utils import timezone
from django.conf import settings

from app.celery import app
from discord.client import DiscordClient
from fleets.models import EveFleet, EveFleetInstance, EveStandingFleet

discord_client = DiscordClient()
logger = logging.getLogger(__name__)

FLEET_SCHEDULE_CHANNEL_ID = settings.DISCORD_FLEET_SCHEDULE_CHANNEL_ID


def get_fleet_emoji(fleet_type):
    """Get the emoji string in format <:name:id> for a fleet type"""
    # Convert fleet_type underscore to hyphen for matching (non_strategic -> non-strategic)
    emoji_name = fleet_type.replace("_", "-")
    
    # Search through DISCORD_FLEET_EMOJIS to find matching emoji_name
    for settings_key, (name, emoji_id) in settings.DISCORD_FLEET_EMOJIS.items():
        if name == emoji_name and emoji_id:
            return f"<:{name}:{emoji_id}>"
    
    return ""


@app.task()
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


@app.task()
def update_standing_fleet_instances():
    for standing_fleet in EveStandingFleet.objects.filter(end_time=None):
        logger.debug("Updating standing fleet instance %s", standing_fleet.id)
        try:
            standing_fleet.update_fleet_members()
        except Exception as e:
            logger.error(
                "An error occurred while updating standing fleet instance %s: %s",
                standing_fleet.id,
                e,
            )
            logger.debug("Assuming fleet is closed")
            standing_fleet.end_time = timezone.now()
            standing_fleet.save()


@app.task()
def update_fleet_schedule():
    """
    Updates fleet schedule message to display all upcoming fleets
    Message format: <fleet type> | <eve time> | <local discord timestamp> | <fleet commander>
    """
    fleets = (
        EveFleet.objects.filter(start_time__gte=timezone.now())
        .exclude(status="cancelled")
        .order_by("start_time")
        .select_related("location", "audience", "created_by")
    )
    
    # Group fleets by location
    fleets_by_location = {}
    for fleet in fleets:
        if fleet.audience and fleet.audience.add_to_schedule:
            location_name = fleet.location.location_name if fleet.location else "No Location"
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
                fc_mention = f"<@{fleet.fleet_commander.user.discord_user.id}>" if fleet.fleet_commander and fleet.fleet_commander.user and fleet.fleet_commander.user.discord_user else ""
                # pylint: disable=inconsistent-quotes
                message += f"- {fleet_emoji} {fleet.start_time.strftime('%Y-%m-%d %H:%M')} EVE (<t:{int(fleet.start_time.timestamp())}>) {fc_mention}\n"
    payload = {
        "content": message,
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "style": 5,
                        "label": "View Fleet Board",
                        "url": "https://my.minmatar.org/fleets/upcoming/",
                        "disabled": False,
                        "type": 2,
                    },
                    {
                        "style": 5,
                        "label": "New Player Instructions",
                        "url": "https://wiki.minmatar.org/alliance/Academy/new-player-fleet-guide",
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
            logger.warning(
                "Failed to delete message %s: %s", msg["id"], e
            )

    # Post new message
    discord_client.create_message(
        FLEET_SCHEDULE_CHANNEL_ID, payload=payload
    )
