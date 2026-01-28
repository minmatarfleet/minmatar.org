motd_string = """
<font size="13" color="#ffffffff"><u>Fleet Overview</u>
FC: </font><font size="13" color="#ffd98d00"><a href="showinfo:1380//{{fc_character_id}}">{{fc_character_name}}</a></font><font size="13" color="#ffffffff">
Formup: </font><font size="13" color="#ffd98d00"><a href="showinfo:2502//{{station_id}}">{{station_name}}</a>
</font><font size="13" color="#ffffffff">Voice: </font><font size="13" color="#ffffe400"><loc><a href="{{discord_link}}">{{discord_name}}</a>
</font><font size="13" color="#bfffffff">Doctrine: </font><font size="13" color="#ffffe400"><loc><a href="{{doctrine_link}}">{{doctrine_name}}</a>
<br>
</font>Bookmarks: <a href="bookmarkFolder:11785719">MinMil</a>
Broadcast settings: <a href="sharedSetting:b6254caf7710e789c99b506ea2ccdc63dc800d91//1//3">DPS</url> | <a href="sharedSetting:ef2be973427c71f5e3785105ce3751882d14acc8//1//3">Logi</url> | <a href="sharedSetting:d2928f2f783f75d0c9815a843ecf0626500dae1d//1//3">Dual Role</url>
Channels: <a href="joinChannel:player_4a392b7086c611ecaf859abe94f5a39b">Minmatar Logistics Chain</a>
<br>
<font size="13" color="#ff00ff00"><b>Fleet tracking is active, managed by https://my.minmatar.org/.</b></font>
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
