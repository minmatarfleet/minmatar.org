from eveonline.models import EveCorporation


def make_nickname(character, discord_user):
    corp = (
        EveCorporation.objects.filter(
            corporation_id=character.corporation_id
        ).first()
        if character.corporation_id
        else None
    )
    ticker = corp.ticker if corp and corp.ticker else "?"
    nickname = f"[{ticker}] {character.character_name}"
    return nickname
