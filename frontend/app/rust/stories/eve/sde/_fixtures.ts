// Real SDE rows for the EVE/SDE stories (rust/fixtures/sde.json, written by
// rust/scripts/sde_fixtures.mjs from the local snapshot).
import sde from '../../../fixtures/sde.json'
import type { SdeSolarSystem, SdeType } from '@dtypes/sde'

export const SHIPS = sde.ships as SdeType[]
export const MODULES = sde.modules as SdeType[]
export const SYSTEMS = sde.systems as SdeSolarSystem[]

const find = <T>(rows: T[], key: keyof T, name: string): T => {
    const row = rows.find((candidate) => candidate[key] === name)
    if (!row)
        throw new Error(`${name} is not in rust/fixtures/sde.json; rerun rust/scripts/sde_fixtures.mjs`)
    return row
}

export const ship = (name: string) => find(SHIPS, 'type_name', name)
export const module_type = (name: string) => find(MODULES, 'type_name', name)
export const system = (name: string) => find(SYSTEMS, 'system_name', name)
