import type { Locales, CharacterRaces } from '@dtypes/layout_components'
import * as cheerio from 'cheerio';

export const get_zkillboard_character_link = (character_id):string => {
    return `https://zkillboard.com/character/${character_id}/`
}

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
        'amarr': 'amarr-cover',
        'minmatar': 'minmatar-cover',
        'caldari': 'caldari-cover',
        'gallente': 'gallente-cover',
    }

    return covers_by_race[race] ?? covers_by_race.caldari
}

export const parse_eve_html = (html:string):string => {
    const $ = cheerio.load(html)
    const prop_equivalent = {
        size: 'font-size',
        face: 'font-family',
    }

    $('font').each((i, el) => {
        const style = {}
        for (let prop in el.attribs) {
            let val = el.attribs[prop]
            if (prop == 'color')
                val = `#${val.substring(3)}`

            if (prop == 'size')
                val = `${val}px`

            style[prop_equivalent[prop] ?? prop] = val
        }

        $(el).css(style)
        el.tagName = 'span'
    })

    return $.html()
}