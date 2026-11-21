/**
 * Name search over the SDE snapshot for the TypeSearch and SolarSystemSearch
 * components (partials sde_type_search_component / sde_system_search_component).
 *
 * Queries are parameterised; the search text is matched with LIKE after its
 * wildcards are escaped, so `50%` or `_` match literally. Prefix matches rank
 * first, then shorter names, then alphabetical order.
 */
import { sde_db } from '@helpers/sde_db'
import { and, eq, gt, gte, inArray, lt, lte, sql, type SQL, type SQLWrapper } from 'drizzle-orm'
import * as schema from '@/models/sde/schema.ts'

import type { SdeSolarSystem, SdeType, ShipSlotCounts } from '@dtypes/sde'

export const SEARCH_MIN_LENGTH = 2
export const SEARCH_DEFAULT_LIMIT = 20
export const SEARCH_MAX_LIMIT = 50

export const SHIP_CATEGORY_ID = 6

const WORMHOLE_MIN_ID = 31000000
/** Abyssal pockets and other non-navigable systems start here. */
const UNREACHABLE_MIN_ID = 32000000

/** Dogma attribute ids of a hull's slot layout. */
export const SLOT_ATTRIBUTES = {
    high: 14,
    mid: 13,
    low: 12,
    rig: 1137,
    subsystem: 1367,
    turrets: 102,
    launchers: 101,
} as const

/** Escape LIKE wildcards (`%`, `_`) and the escape character itself. */
export function escape_like(term: string): string {
    return term.replace(/[\\%_]/g, (match) => `\\${match}`)
}

/** Trimmed, whitespace-collapsed search text. */
export function normalise_query(query: string | null | undefined): string {
    return (query ?? '').trim().replace(/\s+/g, ' ')
}

/** A limit clamped to 1..SEARCH_MAX_LIMIT; anything unparsable is the default. */
export function clamp_limit(limit: number | string | null | undefined): number {
    const parsed = typeof limit === 'number' ? limit : parseInt(limit ?? '', 10)
    if (!Number.isFinite(parsed) || parsed < 1)
        return SEARCH_DEFAULT_LIMIT
    return Math.min(Math.floor(parsed), SEARCH_MAX_LIMIT)
}

/** Comma-separated ids from a query parameter, positive integers only. */
export function parse_ids(value: string | null | undefined): number[] {
    return (value ?? '')
        .split(',')
        .map((part) => parseInt(part.trim(), 10))
        .filter((id) => Number.isInteger(id) && id > 0)
}

const contains = (column: SQLWrapper, term: string) =>
    sql`${column} LIKE ${`%${escape_like(term)}%`} ESCAPE '\\'`

const starts_with = (column: SQLWrapper, term: string) =>
    sql`${column} LIKE ${`${escape_like(term)}%`} ESCAPE '\\'`

export interface TypeSearchOptions {
    query:          string;
    category_ids?:  number[];
    group_ids?:     number[];
    /** Only types CCP publishes (on the market or in game). Default true. */
    published?:     boolean;
    limit?:         number;
}

/** Types whose name contains the query, with group, category, meta group and (for ships) slots. */
export async function search_types({
    query,
    category_ids = [],
    group_ids = [],
    published = true,
    limit,
}: TypeSearchOptions): Promise<SdeType[]> {
    const term = normalise_query(query)
    if (term.length < SEARCH_MIN_LENGTH)
        return []

    const conditions: SQL[] = [contains(schema.invTypes.typeName, term)]
    if (published)
        conditions.push(sql`${schema.invTypes.published} = 1`)
    if (category_ids.length > 0)
        conditions.push(inArray(schema.invGroups.categoryId, category_ids))
    if (group_ids.length > 0)
        conditions.push(inArray(schema.invTypes.groupId, group_ids))

    const rows = await sde_db.select({
        type_id: schema.invTypes.typeId,
        type_name: schema.invTypes.typeName,
        group_id: schema.invGroups.groupId,
        group_name: schema.invGroups.groupName,
        category_id: schema.invCategories.categoryId,
        category_name: schema.invCategories.categoryName,
        meta_group_id: schema.invMetaGroups.metaGroupId,
        meta_group_name: schema.invMetaGroups.metaGroupName,
    })
    .from(schema.invTypes)
    .innerJoin(schema.invGroups, eq(schema.invTypes.groupId, schema.invGroups.groupId))
    .innerJoin(schema.invCategories, eq(schema.invGroups.categoryId, schema.invCategories.categoryId))
    .leftJoin(schema.invMetaTypes, eq(schema.invTypes.typeId, schema.invMetaTypes.typeId))
    .leftJoin(schema.invMetaGroups, eq(schema.invMetaTypes.metaGroupId, schema.invMetaGroups.metaGroupId))
    .where(and(...conditions))
    .orderBy(
        sql`CASE WHEN ${starts_with(schema.invTypes.typeName, term)} THEN 0 ELSE 1 END`,
        sql`length(${schema.invTypes.typeName})`,
        schema.invTypes.typeName,
    )
    .limit(clamp_limit(limit))

    const types: SdeType[] = rows.map((row) => ({
        type_id: row.type_id,
        type_name: row.type_name ?? '',
        group_id: row.group_id,
        group_name: row.group_name ?? '',
        category_id: row.category_id,
        category_name: row.category_name ?? '',
        meta_group_id: row.meta_group_id ?? null,
        meta_group_name: row.meta_group_name ?? null,
    }))

    const ship_ids = types.filter((type) => type.category_id === SHIP_CATEGORY_ID).map((type) => type.type_id)
    if (ship_ids.length > 0) {
        const slots = await get_ship_slots(ship_ids)
        for (const type of types) {
            const ship_slots = slots.get(type.type_id)
            if (ship_slots)
                type.slots = ship_slots
        }
    }

    return types
}

/** Slot layout per hull, in one query. Hulls without slot attributes are absent. */
export async function get_ship_slots(type_ids: number[]): Promise<Map<number, ShipSlotCounts>> {
    const ids = [...new Set(type_ids.filter((id) => Number.isInteger(id) && id > 0))]
    if (ids.length === 0)
        return new Map()

    const attribute_ids = Object.values(SLOT_ATTRIBUTES)
    const rows = await sde_db.select({
        type_id: schema.dgmTypeAttributes.typeId,
        attribute_id: schema.dgmTypeAttributes.attributeId,
        value: sql<number>`coalesce(${schema.dgmTypeAttributes.valueFloat}, ${schema.dgmTypeAttributes.valueInt}, 0)`,
    })
    .from(schema.dgmTypeAttributes)
    .where(and(
        inArray(schema.dgmTypeAttributes.typeId, ids),
        inArray(schema.dgmTypeAttributes.attributeId, attribute_ids),
    ))

    const slots = new Map<number, ShipSlotCounts>()
    for (const row of rows) {
        if (row.type_id === null)
            continue
        const entry = slots.get(row.type_id) ?? { high: 0, mid: 0, low: 0, rig: 0, subsystem: 0, turrets: 0, launchers: 0 }
        const key = (Object.keys(SLOT_ATTRIBUTES) as (keyof typeof SLOT_ATTRIBUTES)[])
            .find((name) => SLOT_ATTRIBUTES[name] === row.attribute_id)
        if (key)
            entry[key] = Math.round(Number(row.value))
        slots.set(row.type_id, entry)
    }
    return slots
}

export type SystemSecurityFilter = 'any' | 'high' | 'low' | 'null' | 'wormhole'

export const SYSTEM_SECURITY_FILTERS: SystemSecurityFilter[] = ['any', 'high', 'low', 'null', 'wormhole']

export interface SystemSearchOptions {
    query:          string;
    region_ids?:    number[];
    /** By displayed security (see display_security): high 0.5+, low 0.1–0.4, null 0.0 and below (k-space). */
    security?:      SystemSecurityFilter;
    /** Include J-space systems when `security` is `any`. Default true. */
    wormholes?:     boolean;
    limit?:         number;
}

/** Solar systems whose name contains the query, with constellation and region. */
export async function search_solar_systems({
    query,
    region_ids = [],
    security = 'any',
    wormholes = true,
    limit,
}: SystemSearchOptions): Promise<SdeSolarSystem[]> {
    const term = normalise_query(query)
    if (term.length < SEARCH_MIN_LENGTH)
        return []

    const system = schema.mapSolarSystems
    const k_space = lt(system.solarSystemId, WORMHOLE_MIN_ID)
    const conditions: (SQL | undefined)[] = [
        contains(system.solarSystemName, term),
        lt(system.solarSystemId, UNREACHABLE_MIN_ID),
    ]
    if (region_ids.length > 0)
        conditions.push(inArray(system.regionId, region_ids))

    // Thresholds follow display_security(): 0.45 shows 0.5, anything above 0 shows at least 0.1.
    if (security === 'high')
        conditions.push(and(k_space, gte(system.security, 0.45)))
    else if (security === 'low')
        conditions.push(and(k_space, gt(system.security, 0), lt(system.security, 0.45)))
    else if (security === 'null')
        conditions.push(and(k_space, lte(system.security, 0)))
    else if (security === 'wormhole')
        conditions.push(gte(system.solarSystemId, WORMHOLE_MIN_ID))
    else if (!wormholes)
        conditions.push(k_space)

    const rows = await sde_db.select({
        system_id: system.solarSystemId,
        system_name: system.solarSystemName,
        security: system.security,
        sun_type_id: system.sunTypeId,
        constellation_id: schema.mapConstellations.constellationId,
        constellation_name: schema.mapConstellations.constellationName,
        region_id: schema.mapRegions.regionId,
        region_name: schema.mapRegions.regionName,
    })
    .from(system)
    .innerJoin(schema.mapConstellations, eq(system.constellationId, schema.mapConstellations.constellationId))
    .innerJoin(schema.mapRegions, eq(system.regionId, schema.mapRegions.regionId))
    .where(and(...conditions))
    .orderBy(
        sql`CASE WHEN lower(${system.solarSystemName}) = lower(${term}) THEN 0 WHEN ${starts_with(system.solarSystemName, term)} THEN 1 ELSE 2 END`,
        system.solarSystemName,
    )
    .limit(clamp_limit(limit))

    return rows.map((row) => ({
        system_id: row.system_id,
        system_name: row.system_name ?? '',
        security: row.security ?? 0,
        sun_type_id: row.sun_type_id ?? null,
        constellation_id: row.constellation_id,
        constellation_name: row.constellation_name ?? '',
        region_id: row.region_id,
        region_name: row.region_name ?? '',
    }))
}
