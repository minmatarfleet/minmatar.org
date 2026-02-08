# Section templates; compose in get_motd(). Each section is self-contained (all <font> closed).
# role_volunteers: list of (role_label, [(character_id, character_name), ...]) for critical roles.

SECTION_HEADER = """<font size="13" color="#ffffffff">Fleet Overview</font>"""

SECTION_FC = """<font size="13" color="#ffffffff">FC: <a href="showinfo:1380//{{fc_character_id}}">{{fc_character_name}}</a></font>"""

# One line per role: "- Role Label: <char1> <char2> ..."
SECTION_ROLE_LINE = """- {{role_label}}: {{character_links}}"""

SECTION_FORMUP = """<font size="13" color="#ffffffff">Staging: </font><font size="13" color="#ffd98d00"><a href="showinfo:2502//{{station_id}}">{{station_name}}</a></font>"""

SECTION_VOICE = """<font size="13" color="#ffffffff">Voice: </font><font size="13" color="#ffffe400"><loc><a href="{{discord_link}}">{{discord_name}}</a></loc></font>"""

SECTION_DOCTRINE = """<font size="13" color="#bfffffff">Doctrine: </font><font size="13" color="#ffffe400"><loc><a href="{{doctrine_link}}">{{doctrine_name}}</a></loc>
<br>
</font>"""

# Links section: header + bookmarks / broadcast / channels (white font)
SECTION_LINKS_HEADER = """<font size="13" color="#ffffffff">Links</font>"""
SECTION_LINKS_BOOKMARKS = """<font size="13" color="#ffffffff">Bookmarks: <a href="bookmarkFolder:11785719">Minmil</a></font>"""
SECTION_LINKS_BROADCAST = """<font size="13" color="#ffffffff">Broadcast: <a href="sharedSetting:b6254caf7710e789c99b506ea2ccdc63dc800d91//1//3">DPS</a>, <a href="sharedSetting:ef2be973427c71f5e3785105ce3751882d14acc8//1//3">Logi</a>, <a href="sharedSetting:d2928f2f783f75d0c9815a843ecf0626500dae1d//1//3">Dual</a></font>"""
SECTION_LINKS_CHANNELS = """<font size="13" color="#ffffffff">Channels: <a href="joinChannel:player_4a392b7086c611ecaf859abe94f5a39b">Minmatar Logistics Chain</a></font>"""

# At bottom when roles are missing: intro line, then bulleted list, then volunteer link
SECTION_MISSING_HEADER = """<font size="13" color="#ffffffff">Some fleet roles are missing:</font>"""
SECTION_MISSING_BULLET = (
    """<font size="13" color="#ffffffff">- {{item}}</font>"""
)
SECTION_MISSING_LINK = """<font size="13" color="#ffffffff"><loc><a href="{{volunteer_url}}">Click here to volunteer</a></loc>.</font>"""


def _role_character_link(character_id, character_name):
    return f'<a href="showinfo:1380//{character_id}">{character_name}</a>'


def get_motd(
    fc_character_id,
    fc_character_name,
    station_id,
    station_name,
    discord_link,
    discord_name,
    doctrine_link,
    doctrine_name,
    role_volunteers=None,
    missing_roles=None,
    volunteer_url=None,
):
    """
    role_volunteers: optional list of (role_label, [(character_id, character_name), ...])
    missing_roles: optional list of short strings e.g. ["Logi Anchor", "Links (Armor)", "1 more Cyno"]
    volunteer_url: optional URL to the volunteer page (shown when missing_roles is non-empty)
    """
    parts = [
        SECTION_HEADER,
        SECTION_FC.replace(
            "{{fc_character_id}}", str(fc_character_id)
        ).replace("{{fc_character_name}}", str(fc_character_name)),
    ]

    if role_volunteers:
        for role_label, characters in role_volunteers:
            character_links = " ".join(
                _role_character_link(cid, cname) for cid, cname in characters
            )
            line = SECTION_ROLE_LINE.replace(
                "{{role_label}}", role_label
            ).replace("{{character_links}}", character_links or "")
            parts.append(
                '<font size="13" color="#ffffffff">' + line + "</font>"
            )

    if station_id is not None and station_name:
        parts.append(
            SECTION_FORMUP.replace("{{station_id}}", str(station_id)).replace(
                "{{station_name}}", str(station_name)
            )
        )

    parts.append(
        SECTION_VOICE.replace("{{discord_link}}", str(discord_link)).replace(
            "{{discord_name}}", str(discord_name)
        )
    )

    if doctrine_link and doctrine_name:
        parts.append(
            SECTION_DOCTRINE.replace(
                "{{doctrine_link}}", str(doctrine_link)
            ).replace("{{doctrine_name}}", str(doctrine_name))
        )

    parts.append("")  # newline after overview section

    parts.extend(
        [
            SECTION_LINKS_HEADER,
            SECTION_LINKS_BOOKMARKS,
            SECTION_LINKS_BROADCAST,
            SECTION_LINKS_CHANNELS,
        ]
    )

    parts.append("")  # newline after links section

    if missing_roles and volunteer_url:
        parts.append(SECTION_MISSING_HEADER)
        for role in missing_roles:
            parts.append(SECTION_MISSING_BULLET.replace("{{item}}", role))
        parts.append(
            SECTION_MISSING_LINK.replace("{{volunteer_url}}", volunteer_url)
        )

    return "\n".join(parts)
