def get_fleet_discord_notification(
    fleet_id,
    fleet_type,
    fleet_commander_name,
    fleet_commander_id,
    fleet_description,
):
    payload = {
        "content": "@everyone",
        "components": [
            {
                "type": 1,
                "components": [
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
                "title": "INCOMING PING TRANSMISSION...",
                "description": f"TYPE: {fleet_type}\n TIME: NOW\n\n {fleet_description}",
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
