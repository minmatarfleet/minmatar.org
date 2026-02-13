from eveonline.models import EveCorporation

# Discord API: nicknames must be 1-32 characters (400 Bad Request otherwise).
DISCORD_NICKNAME_MAX_LENGTH = 32


def make_nickname(character, discord_user):
    corp = (
        EveCorporation.objects.filter(
            corporation_id=character.corporation_id
        ).first()
        if character.corporation_id
        else None
    )
    ticker = corp.ticker if corp and corp.ticker else "?"
    prefix = f"[{ticker}] "
    name_part = character.character_name or ""
    full = prefix + name_part
    if len(full) <= DISCORD_NICKNAME_MAX_LENGTH:
        return full
    max_name_len = DISCORD_NICKNAME_MAX_LENGTH - len(prefix)
    if max_name_len <= 0:
        return prefix.strip()[:DISCORD_NICKNAME_MAX_LENGTH]
    truncated = (
        (name_part[: max_name_len - 1] + "…") if max_name_len > 1 else "…"
    )
    return prefix + truncated
