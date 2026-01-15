def get_fleet_discord_notification(
    fleet_id,
    fleet_type,
    fleet_location,
    fleet_audience,
    fleet_commander_name,
    fleet_commander_id,
    fleet_description,
    fleet_voice_channel,
    fleet_voice_channel_link,
    fleet_doctrine=None,
    fleet_start_time=None,
    is_pre_ping=False,
    content="@everyone",
):
    description = ""
    description += f"**TYPE**: {fleet_type.upper()}\n"
    if is_pre_ping:
        # pylint: disable=inconsistent-quotes
        description += f"**START TIME**: {fleet_start_time.strftime('%Y-%m-%d %H:%M')} EVE | <t:{int(fleet_start_time.timestamp())}> LOCAL\n"
    else:
        if fleet_voice_channel:
            description += f"**VOICE CHANNEL**: MINMATAR FLEET | {fleet_voice_channel.upper()}\n"
    description += f"**LOCATION**: {fleet_location.upper()}\n"
    description += f"**AUDIENCE**: {fleet_audience.upper()}\n"
    description += f"\n**OBJECTIVE**: {fleet_description}\n"

    if is_pre_ping:
        title = "FLEET PRE-PING"
    else:
        title = "INCOMING PING TRANSMISSION..."

    payload = {
        "content": content,
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "style": 5,
                        "label": "Join Voice Channel",
                        "url": (
                            fleet_voice_channel_link
                            if fleet_voice_channel_link
                            else "https://discord.gg/minmatar"
                        ),
                        "disabled": is_pre_ping
                        or not fleet_voice_channel_link,
                        "type": 2,
                    },
                    {
                        "style": 5,
                        "label": "View Fleet Information",
                        "url": f"https://my.minmatar.org/fleets/history/{fleet_id}",
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
        "embeds": [
            {
                "type": "rich",
                "title": title,
                "description": description,
                "color": 0x18ED09,
                "author": {
                    "name": f"{fleet_commander_name}",
                    "icon_url": f"https://images.evetech.net/characters/{fleet_commander_id}/portrait?size=32",
                },
                "url": "https://my.minmatar.org/",
                "footer": {
                    "text": "Minmatar Fleet FC Team",
                    "icon_url": "https://minmatar.org/wp-content/uploads/2023/04/Logo13.png",
                },
            }
        ],
    }
    return payload
