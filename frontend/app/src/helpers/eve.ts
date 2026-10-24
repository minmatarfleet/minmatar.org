import type { Locales, CharacterRaces, Damage } from '@dtypes/layout_components'
import * as cheerio from 'cheerio';
import { decode_unicode_escapes, get_parenthesis_content_last } from '@helpers/string'
import type { CombatLogItem } from '@dtypes/api.minmatar.org'
import { get_item_id } from '@helpers/sde/items'
import { SHIP_GROUP_NAMES, ship_group_icon } from '@helpers/ship_groups'

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
        'mercenary_den': 85230,
        'player_owned_customs_office': 2233,
        'player_owned_starbase': 20059,
    }

    return STRUCTURE_TYPE_BY_ID[structure_type] ?? null
}

export const get_ship_type_icon = (ship_type:string):string | null => ship_group_icon(ship_type)

export const SHIP_TYPES_SORTED = SHIP_GROUP_NAMES

const METERS_IN_A_YEAR_LIGHT = 9460528400000000

export const get_distance_among_systems = (system_a:sde_system, system_b:sde_system):number => {
    return Math.sqrt(Math.pow((system_b.x ?? 0) - (system_a.x ?? 0), 2) + Math.pow((system_b.y ?? 0) - (system_a.y ?? 0), 2) + Math.pow((system_b.z ?? 0) - (system_a.z ?? 0), 2)) / METERS_IN_A_YEAR_LIGHT
}

import type { sde_system } from '@helpers/sde/map'
import { get_systems_coordinates } from '@helpers/sde/map'
import type { SystemCardInfo } from '@dtypes/layout_components'

export const get_moon_systems = async (origin_system_name:string, distance:number, same_region:boolean) => {
    const constellation_systems:SystemCardInfo[] = []

    const sde_systems = await get_systems_coordinates()

    const origin_system = sde_systems.find((sde_system) => sde_system.solarSystemName === origin_system_name)

    if (origin_system === undefined)
        throw new Error('Origin system invalid')
    
    sde_systems.forEach((sde_system) => {
        if (same_region && sde_system.regionName !== origin_system.regionName) return true

        const distance_yl = get_distance_among_systems(origin_system, sde_system)

        if (distance_yl > distance) return true

        constellation_systems.push({
            system_name: sde_system.solarSystemName,
            system_id: sde_system.solarSystemId,
            sun_type_id: sde_system.sunTypeId,
            distance_yl: distance_yl,
            region_name: sde_system.regionName,
            constellation_name: sde_system.constellationName,
            security: sde_system.security,
        })
    })

    return constellation_systems.sort((a, b) => a.distance_yl - b.distance_yl)
}

export const sec_status_class = (security:string):string => {
    const SEC_CLASS = {
        '1.0': 'text-status-1',
        '0.9': 'text-status-point-9',
        '0.8': 'text-status-point-8',
        '0.7': 'text-status-point-7',
        '0.6': 'text-status-point-6',
        '0.5': 'text-status-point-5',
        '0.4': 'text-status-point-4',
        '0.3': 'text-status-point-3',
        '0.2': 'text-status-point-2',
        '0.1': 'text-status-point-1',
        '0': 'text-status-null',
    }

    return SEC_CLASS[security] ?? 'text-status-null'
}

const CAPSULE_TYPE_ID = 670

export const parse_damage_from_logs = async (enemies:CombatLogItem[]) => {
    const damage = await Promise.all(enemies.map(async enemy => {
        const player_ship = await get_parenthesis_content_last(enemy.name)
        const enemy_name = player_ship ? player_ship : enemy.name

        return {
            name: enemy.name,
            item_type: await get_item_id(enemy_name) ?? CAPSULE_TYPE_ID,
            total_from: enemy.damage_from,
            volleys_from: enemy.volleys_from,
            dps_from: enemy.avg_from,
            max_from: enemy.max_from,
            total_to: enemy.damage_to,
            volleys_to: enemy.volleys_to,
            dps_to: enemy.avg_to,
            max_to: enemy.max_to,

        } as Damage
    }))

    return damage
}

import { useTranslations } from '@i18n/utils';

const t = useTranslations('en')

export const structure_type_with_translations = [ 'player_owned_customs_office', 'mercenary_den', 'player_owned_starbase' ] as const
export type StructureTypeWithTranslation = typeof structure_type_with_translations[number]

export const get_selected_item_translation = (system:string, planet: string, timer:Date) => {
    return `${system} - ${t('planet')} ${planet}\r\n`+
            `0 km\r\n`+
            `Reinforced until ${format_selected_item_date(timer)}`
}

function format_selected_item_date(date:Date) {
    const pad = num => String(num).padStart(2, '0')
    const year = date.getFullYear()
    const month = pad(date.getMonth() + 1)
    const day = pad(date.getDate())
    const hours = pad(date.getHours())
    const minutes = pad(date.getMinutes())
    const seconds = pad(date.getSeconds())

    return `${year}.${month}.${day} ${hours}:${minutes}:${seconds}`
}

