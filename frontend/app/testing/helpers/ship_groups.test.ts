import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import Database from 'better-sqlite3'

import sde_fixture from './fixtures/sde_ship_groups.json'
import {
    DEFAULT_SHIP_WEIGHT,
    SHIP_GROUPS,
    SHIP_GROUP_NAMES,
    ship_group_icon,
    ship_group_index,
    ship_size_rank,
    ship_weight,
    is_capital_group,
} from '@helpers/ship_groups'

// The lists ship_groups.ts replaced, restricted to names that exist in the SDE.
// (They also carried names no SDE group has: 'Logistics Crusiers', 'Recon Ship',
// 'Battlecruiser', 'Capital', 'Super Capital', 'Super Carrier', 'Command
// Carrier', 'Mining Frigate', 'Industrial', 'Transport Ship', 'Jump Freighters',
// 'Unclassified', and SHIP_WEIGHT keys 'Supercapital', 'Supercarrier' (sic, it
// matched), 'Miningfrigate', 'Miningbarge', 'Industrialcommand'.)
const LEGACY_SORTED_REAL = [
    'Frigate', 'Electronic Attack Ship', 'Assault Frigate', 'Logistics Frigate', 'Covert Ops',
    'Stealth Bomber', 'Interceptor', 'Destroyer', 'Interdictor', 'Command Destroyer',
    'Tactical Destroyer', 'Cruiser', 'Heavy Assault Cruiser', 'Heavy Interdiction Cruiser',
    'Logistics', 'Strategic Cruiser', 'Force Recon Ship', 'Combat Recon Ship',
    'Combat Battlecruiser', 'Attack Battlecruiser', 'Command Ship', 'Battleship', 'Marauder',
    'Black Ops', 'Dreadnought', 'Lancer Dreadnought', 'Carrier', 'Force Auxiliary', 'Titan',
    'Expedition Frigate', 'Mining Barge', 'Freighter', 'Industrial Command Ship',
]

const LEGACY_HULL_SIZES_REAL: string[][] = [
    ['Frigate', 'Electronic Attack Ship', 'Assault Frigate', 'Logistics Frigate', 'Covert Ops', 'Stealth Bomber', 'Interceptor', 'Expedition Frigate'],
    ['Destroyer', 'Interdictor', 'Command Destroyer', 'Tactical Destroyer'],
    ['Cruiser', 'Heavy Assault Cruiser', 'Heavy Interdiction Cruiser', 'Logistics', 'Strategic Cruiser', 'Force Recon Ship', 'Combat Recon Ship', 'Mining Barge'],
    ['Combat Battlecruiser', 'Attack Battlecruiser', 'Command Ship'],
    ['Battleship', 'Marauder', 'Black Ops'],
    ['Dreadnought', 'Lancer Dreadnought', 'Carrier', 'Force Auxiliary', 'Freighter', 'Industrial Command Ship'],
    ['Titan'],
]

// SHIP_WEIGHT entries whose key matched a real group.
const LEGACY_WEIGHTS_REAL: Record<string, number> = {
    'Frigate': 50, 'Electronic Attack Ship': 50, 'Assault Frigate': 50, 'Logistics Frigate': 50,
    'Covert Ops': 50, 'Stealth Bomber': 50, 'Interceptor': 50, 'Destroyer': 100, 'Interdictor': 100,
    'Command Destroyer': 100, 'Tactical Destroyer': 100, 'Cruiser': 200, 'Heavy Assault Cruiser': 200,
    'Heavy Interdiction Cruiser': 200, 'Logistics': 200, 'Strategic Cruiser': 200,
    'Force Recon Ship': 200, 'Combat Recon Ship': 200, 'Combat Battlecruiser': 300,
    'Attack Battlecruiser': 300, 'Command Ship': 300, 'Battleship': 500, 'Marauder': 500,
    'Black Ops': 500, 'Dreadnought': 700, 'Lancer Dreadnought': 700, 'Carrier': 600,
    'Force Auxiliary': 700, 'Supercarrier': 700, 'Titan': 900, 'Expedition Frigate': 50,
    'Freighter': 500,
}

const LEGACY_CAPITALS_REAL = [
    'Dreadnought', 'Lancer Dreadnought', 'Carrier', 'Force Auxiliary', 'Supercarrier', 'Titan',
    'Capital Industrial Ship', 'Freighter', 'Jump Freighter',
]

const SDE_PATHS = ['src/data/sde-3409592.sqlite', 'src/data/sde-3316380.sqlite']

describe('ship group table', () => {
    it('only uses group names that exist in the SDE', () => {
        const known = new Set(sde_fixture.groups)
        expect(SHIP_GROUP_NAMES.filter(name => !known.has(name))).toEqual([])
        expect(new Set(SHIP_GROUP_NAMES).size).toBe(SHIP_GROUP_NAMES.length)
    })

    it('covers every published SDE ship group', () => {
        const listed = new Set(SHIP_GROUP_NAMES)
        expect(sde_fixture.groups.filter(name => !listed.has(name))).toEqual([])
    })

    it.runIf(SDE_PATHS.some(path => existsSync(path)))('matches the local SDE snapshot', () => {
        const path = SDE_PATHS.find(candidate => existsSync(candidate)) as string
        const db = new Database(path, { readonly: true, fileMustExist: true })
        const rows = db.prepare('SELECT groupName FROM invGroups WHERE categoryID = 6 AND published = 1').all() as { groupName: string }[]
        db.close()
        const sde = new Set(rows.map(row => row.groupName))
        expect(SHIP_GROUP_NAMES.filter(name => !sde.has(name))).toEqual([])
    })

    it('gives every group a numeric weight and an existing icon', () => {
        for (const entry of SHIP_GROUPS) {
            expect(Number.isFinite(entry.weight), entry.group).toBe(true)
            expect(Number.isFinite(ship_weight(entry.group)), entry.group).toBe(true)
            if (entry.icon)
                expect(existsSync(`public/images/icons/ships/${entry.icon}`), entry.icon).toBe(true)
        }
        expect(ship_weight(undefined)).toBe(DEFAULT_SHIP_WEIGHT)
        expect(ship_weight('Not A Group')).toBe(DEFAULT_SHIP_WEIGHT)
        // These were NaN in the fitting viewer (misspelled or missing keys).
        for (const name of ['Supercarrier', 'Jump Freighter', 'Hauler', 'Mining Barge', 'Industrial Command Ship'])
            expect(Number.isFinite(ship_weight(name)), name).toBe(true)
    })
})

describe('parity with the hand-copied lists it replaced', () => {
    it('keeps the list order for groups the old list knew', () => {
        const kept = SHIP_GROUP_NAMES.filter(name => LEGACY_SORTED_REAL.includes(name))
        expect(kept).toEqual(LEGACY_SORTED_REAL)
    })

    it('keeps the doctrine size bucket and in-bucket order for groups the old table knew', () => {
        LEGACY_HULL_SIZES_REAL.forEach((groups, size) => {
            for (const name of groups)
                expect(ship_size_rank(name), name).toBe(size)
            const by_list_order = [...groups].sort((a, b) => ship_group_index(a) - ship_group_index(b))
            expect(by_list_order).toEqual(groups)
        })
    })

    it('keeps the camera weight for groups the old table matched', () => {
        for (const [name, weight] of Object.entries(LEGACY_WEIGHTS_REAL))
            expect(ship_weight(name), name).toBe(weight)
    })

    it('keeps the capital set for real groups', () => {
        expect(SHIP_GROUP_NAMES.filter(is_capital_group).sort()).toEqual([...LEGACY_CAPITALS_REAL].sort())
    })

    it('keeps the icon for groups the old icon map knew', () => {
        expect(ship_group_icon('Titan')).toBe('Isis_titan.png')
        expect(ship_group_icon('Carrier')).toBe('Isis_supercapital.png')
        expect(ship_group_icon('Expedition Frigate')).toBe('Isis_miningfrigate.png')
        expect(ship_group_icon('Freighter')).toBe('Isis_industrial.png')
        expect(ship_group_icon('Not A Group')).toBe(null)
    })

    it('sorts unknown groups first, as indexOf did', () => {
        expect(ship_group_index('Not A Group')).toBe(-1)
    })
})

