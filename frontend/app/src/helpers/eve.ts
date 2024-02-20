import type { Locales, CharacterRaces } from '@dtypes/layout_components'

export const get_character_faction = (race_id:number, locale:Locales = 'en'):CharacterRaces => {
    const faction_by_race_id = {
        1: 'caldari',
        2: 'minmatar',
        4: 'amarr',
        8: 'gallente'
    }

    return faction_by_race_id[race_id] ?? 'unknown'
}

export const get_race_cover_image = (race:CharacterRaces):string => {
    const covers_by_race = {
        'amarr': '/images/character-info-amarr-cover.jpg',
        'minmatar': '/images/character-info-minmatar-cover.jpg',
        'caldari': '/images/character-info-caldari-cover.jpg',
        'gallente': '/images/character-info-gallente-cover.jpg'
    }

    return covers_by_race[race] ?? covers_by_race.caldari
}