import type { Locales, CharacterRaces, Damage } from '@dtypes/layout_components'
import * as cheerio from 'cheerio';
import { decode_unicode_escapes, get_parenthesis_content_last } from '@helpers/string'
import type { CombatLogItem } from '@dtypes/api.minmatar.org'
import { get_item_id } from '@helpers/sde/items'

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

export const get_ship_type_icon = (ship_type:string):string => {
    const SHIP_TYPE_ICONS = {
        'Frigate': 'Isis_frigate.png',
        'Electronic Attack Ship': 'Isis_frigate.png',
        'Assault Frigate': 'Isis_frigate.png',
        'Logistics Frigate': 'Isis_frigate.png',
        'Covert Ops': 'Isis_frigate.png',
        'Stealth Bomber': 'Isis_frigate.png',
        'Interceptor': 'Isis_frigate.png',
        'Destroyer': 'Isis_destroyer.png',
        'Interdictor': 'Isis_destroyer.png',
        'Command Destroyer': 'Isis_destroyer.png',
        'Tactical Destroyer': 'Isis_destroyer.png',
        'Cruiser': 'Isis_cruiser.png',
        'Heavy Assault Cruiser': 'Isis_cruiser.png',
        'Heavy Interdiction Cruiser': 'Isis_cruiser.png',
        'Logistics': 'Isis_cruiser.png',
        'Logistics Crusiers': 'Isis_cruiser.png',
        'Strategic Cruiser': 'Isis_cruiser.png',
        'Recon Ship': 'Isis_cruiser.png',
        'Force Recon Ship': 'Isis_cruiser.png',
        'Combat Recon Ship': 'Isis_cruiser.png',
        'Battlecruiser': 'Isis_battlecruiser.png',
        'Combat Battlecruiser': 'Isis_battlecruiser.png',
        'Attack Battlecruiser': 'Isis_battlecruiser.png',
        'Command Ship': 'Isis_battlecruiser.png',
        'Battleship': 'Isis_battleship.png',
        'Marauder': 'Isis_battleship.png',
        'Black Ops': 'Isis_battleship.png',
        'Capital': 'Isis_capital.png',
        'Dreadnought': 'Isis_capital.png',
        'Lancer Dreadnought': 'Isis_capital.png',
        'Carrier': 'Isis_supercapital.png',
        'Force Auxiliary': 'Isis_supercapital.png',
        'Super Capital': 'Isis_supercapital.png',
        'Super Carrier': 'Isis_supercarrier.png',
        'Titan': 'Isis_titan.png',
        'Mining Frigate': 'Isis_miningfrigate.png',
        'Expedition Frigate': 'Isis_miningfrigate.png',
        'Mining Barge': 'Isis_miningbarge.png',
        'Industrial': 'Isis_industrial.png',
        'Transport Ship': 'Isis_industrial.png',
        'Freighter': 'Isis_industrial.png',
        'Jump Freighters': 'Isis_freighter.png',
        'Industrial Command Ship': 'Isis_industrialcommand.png',
    }

    return SHIP_TYPE_ICONS[ship_type] ?? null
}

export const SHIP_TYPES_SORTED = [
    'Frigate',
    'Electronic Attack Ship',
    'Assault Frigate',
    'Logistics Frigate',
    'Covert Ops',
    'Stealth Bomber',
    'Interceptor',
    'Destroyer',
    'Interdictor',
    'Command Destroyer',
    'Tactical Destroyer',
    'Cruiser',
    'Heavy Assault Cruiser',
    'Heavy Interdiction Cruiser',
    'Logistics',
    'Logistics Crusiers',
    'Strategic Cruiser',
    'Recon Ship',
    'Force Recon Ship',
    'Combat Recon Ship',
    'Battlecruiser',
    'Combat Battlecruiser',
    'Attack Battlecruiser',
    'Command Ship',
    'Battleship',
    'Marauder',
    'Black Ops',
    'Capital',
    'Dreadnought',
    'Lancer Dreadnought',
    'Carrier',
    'Force Auxiliary',
    'Super Capital',
    'Super Carrier',
    'Titan',
    'Mining Frigate',
    'Expedition Frigate',
    'Mining Barge',
    'Industrial',
    'Transport Ship',
    'Freighter',
    'Jump Freighters',
    'Industrial Command Ship',
    'Unclassified',
]

const METERS_IN_A_YEAR_LIGHT = 9460528400000000

export const get_distance_among_systems = (system_a:sde_system, system_b:sde_system):number => {
    return Math.sqrt(Math.pow((system_b.x ?? 0) - (system_a.x ?? 0), 2) + Math.pow((system_b.y ?? 0) - (system_a.y ?? 0), 2) + Math.pow((system_b.z ?? 0) - (system_a.z ?? 0), 2)) / METERS_IN_A_YEAR_LIGHT
}

import type { sde_system } from '@helpers/sde/map'
import { get_systems_coordinates } from '@helpers/sde/map'
import type { SystemCardInfo } from '@dtypes/layout_components'

export const get_systems_at_range = async (origin_system_name:string, years_light:number) => {
    const systems_at_range:SystemCardInfo[] = []

    const sde_systems = await get_systems_coordinates()

    const origin_system = sde_systems.find((sde_system) => sde_system.solarSystemName === origin_system_name)

    if (origin_system === undefined)
        throw new Error('Origin system invalid')
    
    sde_systems.forEach((sde_system) => {
        const distance_yl = get_distance_among_systems(origin_system, sde_system)

        if (distance_yl > years_light) return true

        systems_at_range.push({
            system_name: sde_system.solarSystemName,
            system_id: sde_system.sunTypeId,
            sun_type_id: sde_system.sunTypeId,
            distance_yl: distance_yl,
            region_name: sde_system.regionName,
            constellation_name: sde_system.constellationName,
            security: sde_system.security,
        })
    })

    return systems_at_range.sort((a, b) => a.distance_yl - b.distance_yl)
}

export const get_constellation_systems = async (constellation_name:string, origin_system_name:string) => {
    const constellation_systems:SystemCardInfo[] = []

    const sde_systems = await get_systems_coordinates()

    const origin_system = sde_systems.find((sde_system) => sde_system.solarSystemName === origin_system_name)

    if (origin_system === undefined)
        throw new Error('Origin system invalid')
    
    sde_systems.forEach((sde_system) => {
        if (sde_system.constellationName !== constellation_name) return true

        const distance_yl = get_distance_among_systems(origin_system, sde_system)

        constellation_systems.push({
            system_name: sde_system.solarSystemName,
            system_id: sde_system.sunTypeId,
            sun_type_id: sde_system.sunTypeId,
            distance_yl: distance_yl,
            region_name: sde_system.regionName,
            constellation_name: sde_system.constellationName,
            security: sde_system.security,
        })
    })

    return constellation_systems.sort((a, b) => a.distance_yl - b.distance_yl)
}

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

import { get_parenthesis_content } from '@helpers/string'

export const parse_customs_office_selected_item_text =  (selected_item_text:string, timer:Date) => {
    // Customs Office (Sosala I) [Black Omega Security]
    // 99 km

    // into

    // Sosala - code minmatar at markeedragon
    // 48 km
    // Reinforced until 2024.06.30 00:04:16

    const system = get_parenthesis_content(selected_item_text)

    return `${system} - Customs Office\n0 km\nReinforced until ${format_selected_item_date(timer)}`
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

export const SHIP_WEIGHT = {
    'Frigate': 50,
    'Electronic Attack Ship': 50,
    'Assault Frigate': 50,
    'Logistics Frigate': 50,
    'Covert Ops': 50,
    'Stealth Bomber': 50,
    'Interceptor': 50,
    'Destroyer': 100,
    'Interdictor': 100,
    'Command Destroyer': 100,
    'Tactical Destroyer': 100,
    'Cruiser': 200,
    'Heavy Assault Cruiser': 200,
    'Heavy Interdiction Cruiser': 200,
    'Logistics': 200,
    'Logistics Crusiers': 200,
    'Strategic Cruiser': 200,
    'Recon Ship': 200,
    'Force Recon Ship': 200,
    'Combat Recon Ship': 200,
    'Battlecruiser': 300,
    'Combat Battlecruiser': 300,
    'Attack Battlecruiser': 300,
    'Command Ship': 300,
    'Battleship': 500,
    'Marauder': 500,
    'Black Ops': 500,
    'Capital': 700,
    'Dreadnought': 700,
    'Lancer Dreadnought': 700,
    'Carrier': 600,
    'Force Auxiliary': 700,
    'Supercapital': 700,
    'Supercarrier': 700,
    'Titan': 900,
    'Miningfrigate': 50,
    'Expedition Frigate': 50,
    'Miningbarge': 100,
    'Industrial': 300,
    'Transport Ship': 100,
    'Freighter': 500,
    'Jump Freighters': 500,
    'Industrialcommand': 700,
}