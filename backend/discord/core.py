import upsidedown


def make_nickname(character, discord_user):
    corporation = character.corporation

    nickname = f"[{corporation.ticker}] {character.character_name}"

    return nickname
