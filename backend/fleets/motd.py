# Section templates; compose in get_motd(). Each section is self-contained (all <font> closed).
# role_volunteers: list of (role_label, [(character_id, character_name), ...]) for critical roles.

SECTION_HEADER = """<font size="13" color="#ffffffff">Fleet Overview</font>"""

SECTION_FC = """<font size="13" color="#ffffffff">FC: <a href="showinfo:1380//{{fc_character_id}}">{{fc_character_name}}</a></font>"""

# One line per role: "- Role Label: <char1> <char2> ..."
SECTION_ROLE_LINE = """- {{role_label}}: {{character_links}}"""

SECTION_FORMUP = """<font size="13" color="#ffffffff">Staging: </font><font size="13" color="#ffd98d00"><a href="showinfo:2502//{{station_id}}">{{station_name}}</a></font>"""

SECTION_VOICE = """<font size="13" color="#ffffffff">Voice: </font><font size="13" color="#ffffe400"><loc><a href="{{discord_link}}">{{discord_name}}</a></loc></font>"""

SECTION_DOCTRINE = """<font size="13" color="#bfffffff">Doctrine: </font><font size="13" color="#ffffe400"><loc><a href="{{doctrine_link}}">{{doctrine_name}}</a></loc></font>"""

SECTION_DOCTRINE_MISSING = """<font size="13" color="#bfffffff">Doctrine: </font><font size="13" color="#ffffe400"><loc><a href="{{fleet_edit_url}}">Set the doctrine</a></loc></font>"""

# Resources section: header + bookmarks / broadcast / channels (white font)
SECTION_RESOURCES_HEADER = (
    """<font size="13" color="#ffffffff">Resources</font>"""
)
SECTION_RESOURCES_BOOKMARKS = """<font size="13" color="#ffffffff">Bookmarks: <a href="bookmarkFolder:11785719">Minmil</a></font>"""
SECTION_RESOURCES_BROADCAST = """<font size="13" color="#ffffffff">Broadcast: <a href="sharedSetting:b6254caf7710e789c99b506ea2ccdc63dc800d91//1//3">DPS</a>, <a href="sharedSetting:ef2be973427c71f5e3785105ce3751882d14acc8//1//3">Logi</a>, <a href="sharedSetting:d2928f2f783f75d0c9815a843ecf0626500dae1d//1//3">Dual</a></font>"""
SECTION_RESOURCES_CHANNELS = """<font size="13" color="#ffffffff">Channels: <a href="joinChannel:player_4a392b7086c611ecaf859abe94f5a39b">Minmatar Logistics Chain</a></font>"""

# At bottom when roles are missing: one condensed line, then volunteer link


# Fleet-specific composition (no doctrine): header, then "- <a>Hurricane</a>"
SECTION_COMPOSITION_HEADER = (
    """<font size="13" color="#ffffffff">Fits</font>"""
)
SECTION_FIT_LINE = (
    """<font size="13" color="#ffffe400">- {{fit_link}}</font>"""
)

# Refits section: header, then "- <refit>" per fleet refit
SECTION_REFITS_HEADER = """<font size="13" color="#ffffffff">Refits</font>"""
SECTION_REFIT_LINE = (
    """<font size="13" color="#ffffe400">- {{refit_link}}</font>"""
)


def _role_character_link(character_id, character_name):
    return f'<a href="showinfo:1380//{character_id}">{character_name}</a>'


def _fit_link(name, href):
    """Web links need <loc>; in-game ``fitting:`` links must not have it."""
    if not href:
        return str(name)
    if str(href).startswith("fitting:"):
        return f'<a href="{href}">{name}</a>'
    return f'<loc><a href="{href}">{name}</a></loc>'


def _refit_lines(refits):
    """refits: list of (refit_name, refit_href). One linked refit per line."""
    lines = [SECTION_REFITS_HEADER]
    for refit_name, refit_href in refits:
        lines.append(
            SECTION_REFIT_LINE.replace(
                "{{refit_link}}", _fit_link(refit_name, refit_href)
            )
        )
    return lines


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
    fleet_edit_url=None,
    refits=None,
    composition=None,
):
    """
    role_volunteers: optional list of (role_label, [(character_id, character_name), ...])
    fleet_edit_url: optional URL to edit the fleet (shown when no doctrine is set)
    refits: optional list of (refit_name, refit_href) shown under the
        doctrine; refit_href is an in-game ``fitting:`` link or None
    composition: optional list of (fit_name, href|None) for fleets that
        run fleet-specific fits instead of a doctrine (web or ``fitting:``)
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
    parts.append("")  # blank line: fleet info above, ships below

    if doctrine_link and doctrine_name:
        parts.append(
            SECTION_DOCTRINE.replace(
                "{{doctrine_link}}", str(doctrine_link)
            ).replace("{{doctrine_name}}", str(doctrine_name))
        )
    elif composition:
        parts.append(SECTION_COMPOSITION_HEADER)
        parts.extend(
            SECTION_FIT_LINE.replace("{{fit_link}}", _fit_link(name, url))
            for name, url in composition
        )
    elif fleet_edit_url:
        parts.append(
            SECTION_DOCTRINE_MISSING.replace(
                "{{fleet_edit_url}}", str(fleet_edit_url)
            )
        )

    if refits:
        parts.extend(_refit_lines(refits))

    parts.extend(
        [
            "",  # blank line so Resources reads as its own section
            SECTION_RESOURCES_HEADER,
            SECTION_RESOURCES_BOOKMARKS,
            SECTION_RESOURCES_BROADCAST,
            SECTION_RESOURCES_CHANNELS,
        ]
    )

    return "\n".join(parts)
