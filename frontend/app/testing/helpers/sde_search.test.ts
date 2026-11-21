import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import Database from 'better-sqlite3'

import {
    clamp_limit,
    escape_like,
    normalise_query,
    parse_ids,
    search_solar_systems,
    search_types,
    SEARCH_DEFAULT_LIMIT,
    SEARCH_MAX_LIMIT,
} from '@helpers/sde/search'
import { display_security, format_security, meta_group_token, security_band, security_token } from '@helpers/sde/display'

// The SDE queries run against the local snapshot when there is one; CI has none and skips them.
const SDE_PATHS = [process.env.SDE_PATH, 'src/data/sde-3409592.sqlite', 'src/data/sde-3316380.sqlite']
    .filter((path): path is string => Boolean(path))
const sde_path = SDE_PATHS.find((path) => existsSync(path))

const sqlite_loads = (() => {
    try {
        new Database(':memory:').close()
        return true
    } catch {
        return false
    }
})()

const with_sde = Boolean(sde_path) && sqlite_loads
if (with_sde)
    process.env.SDE_PATH = sde_path

describe('display_security', () => {
    it('rounds to one decimal like the EVE client', () => {
        expect(display_security(0.438761248111)).toBe(0.4)     // Amamake
        expect(display_security(0.945913116665)).toBe(0.9)     // Jita
        expect(display_security(0.45)).toBe(0.5)
        expect(display_security(0.449)).toBe(0.4)
        expect(display_security(1)).toBe(1)
    })

    it('shows 0.0–0.05 as 0.1, not null-sec', () => {
        expect(display_security(0.0345)).toBe(0.1)             // Egbinger
        expect(display_security(0)).toBe(0)
    })

    it('keeps negative values and never shows -0.0', () => {
        expect(display_security(-0.1463)).toBe(-0.1)           // HED-GP
        expect(format_security(-0.04)).toBe('0.0')
        expect(format_security(-0.99)).toBe('-1.0')
        expect(format_security(Number.NaN)).toBe('0.0')
    })
})

describe('security_band and security_token', () => {
    it('bands by the displayed value', () => {
        expect(security_band(0.45)).toBe('high')
        expect(security_band(0.44)).toBe('low')
        expect(security_band(0.01)).toBe('low')
        expect(security_band(0)).toBe('null')
        expect(security_band(-0.99, 31001159)).toBe('wormhole')
    })

    it('maps to the --security-status-* tokens', () => {
        expect(security_token(1)).toBe('security-status-1')
        expect(security_token(0.96)).toBe('security-status-1')
        expect(security_token(0.4387)).toBe('security-status-point-4')
        expect(security_token(0.0345)).toBe('security-status-point-1')
        expect(security_token(-0.38)).toBe('security-status-null')
    })
})

describe('meta_group_token', () => {
    it('maps meta groups to their colour tokens', () => {
        expect(meta_group_token('Tech II')).toBe('tech-ii')
        expect(meta_group_token('Officer')).toBe('officer')
        expect(meta_group_token('Premium')).toBeNull()
        expect(meta_group_token(null)).toBeNull()
    })
})

describe('search input helpers', () => {
    it('escapes LIKE wildcards', () => {
        expect(escape_like('50%_off\\')).toBe('50\\%\\_off\\\\')
    })

    it('normalises whitespace', () => {
        expect(normalise_query('  Republic   Fleet ')).toBe('Republic Fleet')
        expect(normalise_query(null)).toBe('')
    })

    it('clamps limits', () => {
        expect(clamp_limit(undefined)).toBe(SEARCH_DEFAULT_LIMIT)
        expect(clamp_limit('abc')).toBe(SEARCH_DEFAULT_LIMIT)
        expect(clamp_limit(0)).toBe(SEARCH_DEFAULT_LIMIT)
        expect(clamp_limit('5')).toBe(5)
        expect(clamp_limit(500)).toBe(SEARCH_MAX_LIMIT)
    })

    it('parses id lists', () => {
        expect(parse_ids('6, 7,x,-1,0')).toEqual([6, 7])
        expect(parse_ids(null)).toEqual([])
    })
})

describe.runIf(with_sde)('search over the local SDE snapshot', () => {
    it('returns nothing for a one-letter query', async () => {
        expect(await search_types({ query: 'R' })).toEqual([])
        expect(await search_solar_systems({ query: ' A ' })).toEqual([])
    })

    it('finds ships with slots, prefix matches first', async () => {
        const ships = await search_types({ query: 'rifter', category_ids: [6] })
        expect(ships[0]).toMatchObject({ type_id: 587, type_name: 'Rifter', group_name: 'Frigate', category_name: 'Ship' })
        expect(ships[0].slots).toMatchObject({ high: 3, mid: 3, low: 4, rig: 3, subsystem: 0 })
        expect(ships.every((ship) => ship.category_id === 6)).toBe(true)
    })

    it('carries the meta group and filters by group', async () => {
        const gyros = await search_types({ query: 'Gyrostabilizer', group_ids: [59], limit: 50 })
        const by_name = new Map(gyros.map((type) => [type.type_name, type.meta_group_name]))
        expect(by_name.get('Gyrostabilizer II')).toBe('Tech II')
        expect(by_name.get('Republic Fleet Gyrostabilizer')).toBe('Faction')
        expect(gyros.every((type) => type.group_id === 59)).toBe(true)
        expect(gyros.some((type) => type.type_name.endsWith('Blueprint'))).toBe(false)
    })

    it('treats LIKE wildcards literally and respects the limit', async () => {
        expect(await search_types({ query: '%%' })).toEqual([])
        expect(await search_types({ query: '__' })).toEqual([])
        expect((await search_types({ query: 'Damage Control', limit: 3 })).length).toBe(3)
    })

    it('finds systems with region and constellation, exact name first', async () => {
        const [first] = await search_solar_systems({ query: 'amamake' })
        expect(first).toMatchObject({ system_id: 30002537, system_name: 'Amamake', constellation_name: 'Hed', region_name: 'Heimatar' })
        expect(first.security).toBeGreaterThan(0.4)
    })

    it('filters systems by security band', async () => {
        const low = await search_solar_systems({ query: 'am', security: 'low', limit: 50 })
        expect(low.length).toBeGreaterThan(0)
        expect(low.every((system) => security_band(system.security, system.system_id) === 'low')).toBe(true)

        const wormholes = await search_solar_systems({ query: 'J16', security: 'wormhole' })
        expect(wormholes.every((system) => system.system_id >= 31000000)).toBe(true)

        const k_space = await search_solar_systems({ query: 'J16', wormholes: false })
        expect(k_space.every((system) => system.system_id < 31000000)).toBe(true)
    })
})
