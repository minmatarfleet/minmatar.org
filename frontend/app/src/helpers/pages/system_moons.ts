import { useTranslations } from '@i18n/utils';

import { fetch_scanned_moons } from '@helpers/fetching/moons'
import { find_system_planets, get_system_id, find_systems_moons, get_system_sun_type_id } from '@helpers/sde/map'
import type { PlanetBasic, MoonBasic, MoonUI, PlanetMoonsUI } from '@dtypes/layout_components'

import { prod_error_messages } from '@helpers/env'

export interface SystemMoonsData {
    sun_type_id?:       number;
    total_scanned?:     number;
    moons?:             MoonBasic[];
    planet_moons?:      PlanetMoonsUI[];
}

export async function get_system_moons_data(auth_token:string, system_name:string, lang:'en' = 'en') {
    const t = useTranslations(lang)

    let planets:PlanetBasic[] = []
    let moons:MoonBasic[] = []
    let scanned_moons:MoonUI[] = []
    let planet_moons:PlanetMoonsUI[] = []
    let total_scanned:number = 0
    let sun_type_id:number

    try {
        const system_id = await get_system_id(system_name)
        planets = await find_system_planets(system_id)
        moons = await find_systems_moons([system_id])
        scanned_moons = await fetch_scanned_moons(auth_token, system_name)
        sun_type_id = await get_system_sun_type_id(system_id)

        planet_moons = planets.map(planet => {
            const planet_moons = moons.filter(moon => moon.name.startsWith(`${planet.name} - Moon`))

            const planet_moons_ui = planet_moons.map(moon => {
                const scanned_moon = scanned_moons.find(scanned_moon => scanned_moon.name === moon.name)
                const is_scanned = scanned_moon !== undefined
                
                if (is_scanned) total_scanned++

                return {
                    id: moon.id,
                    name: moon.name,
                    scanned: is_scanned,
                    monthly_revenue: scanned_moon?.monthly_revenue,
                } as MoonUI
            })

            return {
                id: planet.id,
                name: planet.name,
                type_id: planet.type_id,
                scanned: planet_moons_ui.reduce((c, v) => c + (v.scanned ? 1 : 0), 0),
                moons: planet_moons_ui.sort((a, b) => {
                    let numA = parseInt(a.name.split("Moon ")[1]);
                    let numB = parseInt(b.name.split("Moon ")[1]);
                    
                    return numA - numB;
                }),
            }
        })
    } catch (error) {
        throw new Error(prod_error_messages() ? t('get_all_mains_alts_error') : error.message)
    }

    return {
        sun_type_id: sun_type_id,
        total_scanned: total_scanned,
        moons: moons,
        planet_moons: planet_moons,
    } as SystemMoonsData
}