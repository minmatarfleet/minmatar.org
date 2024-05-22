motd_string = """
<font size="13" color="#ffffffff"><u>Fleet Overview</u>
FC: </font><font size="13" color="#ffd98d00"><a href="showinfo:1380//{{fc_character_id}}">{{fc_character_name}}</a></font><font size="13" color="#ffffffff">
Formup: </font><font size="13" color="#ffd98d00"><a href="showinfo:2502//{{station_id}}">{{station_name}}</a>
</font><font size="13" color="#ffffffff">Voice: </font><font size="13" color="#ffffe400"><loc><a href="{{discord_link}}">{{discord_name}}</a>
</font><font size="13" color="#bfffffff">Doctrine: </font><font size="13" color="#ffffe400"><loc><a href="{{doctrine_link}}">{{doctrine_name}}</a>
<br>
</font><font size="13" color="#ff00a99d"><a href="bookmarkFolder:11785719">Minmil Bookmarks</a></font><font size="13" color="#ffffe400"><a href="https://tools.minmatar.org/fleets/doctrines/stratop-battlecruiser-composition/"> </a>
</font><font size="13" color="#ff6868e1"><a href="joinChannel:player_4a392b7086c611ecaf859abe94f5a39b">Minmatar Logistics Chain</a>
<br>
</font><font size="13" color="#ff00ff00"><b>Fleet tracking is active, managed by https://my.minmatar.org/.</b></font>
"""

standing_fleet_motd = """
<font size="13" color="#ffffffff"><u>Fleet Overview</u>
<br>
FC: </font><font size="13" color="#ffd98d00"><a href="showinfo:1380//{{fc_character_id}}">{{fc_character_name}}</a></font><font size="13" color="#ffffffff">
<br>
Staging: </font><font size="13" color="#ffd98d00"><a href="showinfo:2502//{{station_id}}">{{station_name}}</a>
<br>
</font><font size="13" color="#ffffffff">Voice: </font><font size="13" color="#ffffe400"><loc><a href="{{discord_link}}">{{discord_name}}</a>
<br>
<br>
</font><font size="13" color="#ff00ff00"><b>Fleet tracking is active, managed by https://my.minmatar.org/.</b></font>
"""


def get_motd(
    fc_character_id,
    fc_character_name,
    station_id,
    station_name,
    discord_link,
    discord_name,
    doctrine_link,
    doctrine_name,
):
    return (
        motd_string.replace("{{fc_character_id}}", str(fc_character_id))
        .replace("{{fc_character_name}}", str(fc_character_name))
        .replace("{{station_id}}", str(station_id))
        .replace("{{station_name}}", str(station_name))
        .replace("{{discord_link}}", str(discord_link))
        .replace("{{discord_name}}", str(discord_name))
        .replace("{{doctrine_link}}", str(doctrine_link))
        .replace("{{doctrine_name}}", str(doctrine_name))
    )


def get_standing_motd(
    fc_character_id,
    fc_character_name,
    station_id,
    station_name,
    discord_link,
    discord_name,
):
    return (
        standing_fleet_motd.replace(
            "{{fc_character_id}}", str(fc_character_id)
        )
        .replace("{{fc_character_name}}", str(fc_character_name))
        .replace("{{station_id}}", str(station_id))
        .replace("{{station_name}}", str(station_name))
        .replace("{{discord_link}}", str(discord_link))
        .replace("{{discord_name}}", str(discord_name))
    )
