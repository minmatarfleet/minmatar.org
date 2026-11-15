/**
 * The Fleet Roles guides' ship sections, built from our current doctrines.
 *
 * A guide with `ships_from_doctrines: 'damage'` lists every hull that flies a
 * damage fit in a doctrine today: a fit with three or more weapons and no
 * remote repairers. `'logistics'` lists the hulls whose fits carry a remote
 * repairer. The charges in each fit (loaded and in cargo) feed the
 * ammo charts, matched by name against ammo.json from the SDE.
 */
import { inArray, eq } from 'drizzle-orm'
import * as schema from '@/models/sde/schema.ts'
import { sde_db } from '@helpers/sde_db'
import { parse_eft } from '@helpers/eft'
import ammo from '@/data/fleet-roles/ammo.json'
import type { Doctrine } from '@dtypes/api.minmatar.org'
import type { FleetRoleGuide } from '@/data/fleet-roles'

export type AmmoCharge = {
    type_id: number
    family: string
    em: number
    thermal: number
    kinetic: number
    explosive: number
    size?: number
    range_mult?: number
    tracking_mult?: number
    falloff_mult?: number
    range_km?: number
    explosion_radius_m?: number
    explosion_velocity_ms?: number
    drf?: number
}

export const AMMO = ammo.charges as Record<string, AmmoCharge>

export type AmmoTarget = {
    type_id: number
    signature_m: number
    velocity_ms: number
    armor_resists: Record<'em' | 'thermal' | 'kinetic' | 'explosive', number>
}

/** Hulls the ammo charts show damage against, from the SDE. */
export const AMMO_TARGETS = ammo.targets as Record<string, AmmoTarget>

export type DoctrineSlot = 'primary' | 'secondary' | 'support' | 'utility'

export type ShipFit = {
    doctrine_id: number
    doctrine_name: string
    /** The doctrine's main hull (its first primary fit), shown as the doctrine's icon. */
    doctrine_ship_id: number | null
    slot: DoctrineSlot
    fitting_id: number
    fitting_name: string
}

export type RoleShip = {
    ship_type_id: number
    name: string
    /** Weapon family of the fits, keyed like ammo.json ('projectile', 'cruise_missile', ...) (damage ships only). */
    family: string | null
    fits: ShipFit[]
    /** Charge names the fits carry, in fit order. */
    charges: string[]
}

const SLOTS = [
    ['primary_fittings', 'primary'],
    ['secondary_fittings', 'secondary'],
    ['support_fittings', 'support'],
    ['utility_fittings', 'utility'],
] as const

const WEAPON_GROUP = /( Weapon|^Missile Launcher)/
const REMOTE_REPAIR_GROUP = /^(Remote (Armor|Shield|Hull)|Ancillary Remote|Mutadaptive Remote)/

/** Charge names in a fit: the charge after "Module, Charge", and cargo, in order. */
export function fit_charges(eft: string): string[] {
    const names: string[] = []
    for (const raw of eft.replace(/\r/g, '').split('\n')) {
        const line = raw.trim()
        const loaded = line.match(/^[^[].*?,\s*(.+)$/)
        const cargo = line.match(/^(.+?)\s+x\d+$/)
        const name = (loaded?.[1] ?? cargo?.[1] ?? '').trim()
        if (name && AMMO[name] && !names.includes(name)) names.push(name)
    }
    return names
}

async function group_names(names: string[]): Promise<Map<string, string>> {
    const unique = [...new Set(names)]
    if (unique.length === 0) return new Map()
    const rows = await sde_db
        .select({ name: schema.invTypes.typeName, group: schema.invGroups.groupName })
        .from(schema.invTypes)
        .innerJoin(schema.invGroups, eq(schema.invTypes.groupId, schema.invGroups.groupId))
        .where(inArray(schema.invTypes.typeName, unique))
    return new Map(rows.map((row) => [row.name as string, row.group as string]))
}

export type DoctrineShipKind = 'damage' | 'logistics' | 'listed'

/** Every hull flying a damage or logistics fit in a current doctrine, or the listed hulls' fits. */
export async function doctrine_ships(doctrines: Doctrine[], only?: number[], kind: DoctrineShipKind = 'damage'): Promise<RoleShip[]> {
    type Fit = { doctrine: Doctrine; slot: DoctrineSlot; fitting: Doctrine['primary_fittings'][number] }
    const fits: Fit[] = []
    for (const doctrine of doctrines) {
        if (doctrine.retired) continue
        for (const [field, slot] of SLOTS)
            for (const fitting of doctrine[field] ?? []) fits.push({ doctrine, slot, fitting })
    }

    const parsed = fits.map((fit) => parse_eft(fit.fitting.eft_format))
    const groups = await group_names(parsed.flatMap((p) => p.modules.map((m) => m.name)))

    const ships = new Map<number, RoleShip>()
    fits.forEach((fit, index) => {
        const modules = parsed[index].modules
        const weapons = modules.filter((m) => WEAPON_GROUP.test(groups.get(m.name) ?? '')).length
        const repair_groups = modules.map((m) => groups.get(m.name) ?? '').filter((group) => REMOTE_REPAIR_GROUP.test(group))
        if (kind === 'damage' && (weapons < 3 || repair_groups.length > 0)) return
        if (kind === 'logistics' && repair_groups.length === 0) return
        if (only && !only.includes(fit.fitting.ship_id)) return

        const id = fit.fitting.ship_id
        const ship = ships.get(id) ?? { ship_type_id: id, name: parsed[index].ship, family: null, fits: [], charges: [] }
        if (!ship.fits.some((f) => f.fitting_id === fit.fitting.id && f.doctrine_id === fit.doctrine.id)) {
            ship.fits.push({
                doctrine_id: fit.doctrine.id,
                doctrine_name: fit.doctrine.name,
                doctrine_ship_id: fit.doctrine.primary_fittings?.[0]?.ship_id ?? null,
                slot: fit.slot,
                fitting_id: fit.fitting.id,
                fitting_name: fit.fitting.name,
            })
        }
        if (kind === 'damage')
            for (const charge of fit_charges(fit.fitting.eft_format))
                if (!ship.charges.includes(charge)) ship.charges.push(charge)
        ships.set(id, ship)
    })

    for (const ship of ships.values()) {
        if (kind !== 'damage') continue
        const counts = new Map<string, number>()
        for (const charge of ship.charges) counts.set(AMMO[charge].family, (counts.get(AMMO[charge].family) ?? 0) + 1)
        ship.family = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
        ship.charges = ship.charges.filter((charge) => AMMO[charge].family === ship.family)
    }
    // Hulls the guide names but no doctrine flies today still get a card.
    const missing = (only ?? []).filter((id) => !ships.has(id))
    if (missing.length > 0) {
        const rows = await sde_db
            .select({ id: schema.invTypes.typeId, name: schema.invTypes.typeName })
            .from(schema.invTypes)
            .where(inArray(schema.invTypes.typeId, missing))
        for (const row of rows)
            ships.set(row.id as number, { ship_type_id: row.id as number, name: row.name as string, family: null, fits: [], charges: [] })
    }

    const list = [...ships.values()]
    if (only) list.sort((a, b) => only.indexOf(a.ship_type_id) - only.indexOf(b.ship_type_id))
    return list
}

/** The hulls a guide's live lists count: its doctrine ships, or its ladder. */
export async function role_ship_ids(guide: FleetRoleGuide, doctrines: Doctrine[]): Promise<number[]> {
    if (guide.ships_from_doctrines)
        return (await doctrine_ships(doctrines, guide.ships_only, guide.ships_from_doctrines)).map((ship) => ship.ship_type_id)
    return guide.ladder.map((rung) => rung.ship_type_id)
}
