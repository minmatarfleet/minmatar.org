import type { Locales, CharacterRaces } from '@dtypes/layout_components'
import * as cheerio from 'cheerio';
import { decode_unicode_escapes } from '@helpers/string'

export const get_zkillboard_character_link = (character_id):string => {
    return `https://zkillboard.com/character/${character_id}/`
}

export const get_zkillboard_corporation_link = (corporation_id):string => {
    return `https://zkillboard.com/corporation/${corporation_id}/`
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
    let stripped_html = html
    
    if (html.length >= 3 && (html.startsWith("u'") && html.endsWith("'")))
        stripped_html = html.slice(2, -1);

    const $ = cheerio.load(decode_unicode_escapes(stripped_html))
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

export const get_structure_id = (structure_type:string):number => {
    const STRUCTURE_TYPE_BY_ID = {
        'astrahus': 35832,
        'fortizar': 35833,
        'keepstar': 35834,
        'raitaru': 35825,
        'azbel': 35826,
        'sotiyo': 35827,
        'athanor': 35835,
        'tatara': 35836,
        'tenebrex_cyno_jammer': 37534,
        'pharolux_cyno_beacon': 35840,
        'ansiblex_jump_gate': 35841,
        'orbital_skyhook': 81080,
        'metenox_moon_drill': 81826,
    }

    return STRUCTURE_TYPE_BY_ID[structure_type] ?? null
}