import upsidedown

def make_nickname(character, discord_user):
    corporation = character.corporation

    nickname = f"[{corporation.ticker}] {character.character_name}"

    if discord_user.is_down_under:
        nickname = upsidedown.transform(nickname)

    if discord_user.dress_wearer:
        nickname = f"[👗] {character.character_name}"

    if corporation.ticker == "-DRY-":
        nickname = f"[ω] {character.character_name}"

    return nickname
