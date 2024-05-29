import logging

from django.utils import timezone

from app.celery import app
from discord.client import DiscordClient
from fleets.models import EveFleet, EveFleetInstance, EveStandingFleet

discord_client = DiscordClient()
logger = logging.getLogger(__name__)

FLEET_SCHEDULE_CHANNEL_ID = 1174169403873558658
FLEET_SCHEDULE_MESSAGE_ID = 1244656126302224466


@app.task()
def update_fleet_instances():
    """
    Update fleet instances
    """
    for fleet_instance in EveFleetInstance.objects.filter(end_time=None):
        logger.info("Updating fleet instance %s", fleet_instance.id)
        try:
            fleet_instance.update_is_registered_status()
            fleet_instance.update_fleet_members()
        except Exception as e:
            logger.info(
                "An error occurred while updating fleet instance %s: %s",
                fleet_instance.id,
                e,
            )
            logger.info("Assuming fleet is closed")
            fleet_instance.end_time = timezone.now()
            fleet_instance.save()


@app.task()
def update_standing_fleet_instances():
    for standing_fleet in EveStandingFleet.objects.filter(end_time=None):
        logger.info("Updating standing fleet instance %s", standing_fleet.id)
        try:
            standing_fleet.update_fleet_members()
        except Exception as e:
            logger.info(
                "An error occurred while updating standing fleet instance %s: %s",
                standing_fleet.id,
                e,
            )
            logger.info("Assuming fleet is closed")
            standing_fleet.end_time = timezone.now()
            standing_fleet.save()


@app.task()
def update_fleet_schedule():
    """
    Updates fleet schedule message to display all upcoming fleets
    Message format: <fleet type> | <eve time> | <local discord timestamp> | <fleet commander>
    """
    fleets = EveFleet.objects.filter(start_time__gte=timezone.now()).order_by(
        "start_time"
    )
    message = "## Fleet Schedule\n"
    for fleet in fleets:
        message += f"- {fleet.get_type_display()} | {fleet.start_time.strftime('%Y-%m-%d %H:%M')} EVE | <t:{int(fleet.start_time.timestamp())}> LOCAL | <@{fleet.fleet_commander.token.user.discord_user.id}>\n"

    if not fleets:
        message += "- No upcoming fleets, go touch grass you nerd"
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
                        "url": "https://minmatar.org/guides/new-player-fleet-guide/",
                        "disabled": False,
                        "type": 2,
                    },
                ],
            }
        ],
    }

    if (
        discord_client.get_message(
            FLEET_SCHEDULE_CHANNEL_ID, FLEET_SCHEDULE_MESSAGE_ID
        )["content"]
        == message
    ):
        logger.info("Fleet schedule message is up to date, skipping update")
        return

    discord_client.update_message(
        FLEET_SCHEDULE_CHANNEL_ID, FLEET_SCHEDULE_MESSAGE_ID, payload=payload
    )

    # Create reminder message and delete it
    updated_notification = discord_client.create_message(
        FLEET_SCHEDULE_CHANNEL_ID,
        payload="A new / updated fleet schedule has been posted",
    )

    discord_client.delete_message(
        FLEET_SCHEDULE_CHANNEL_ID, updated_notification["id"]
    )
