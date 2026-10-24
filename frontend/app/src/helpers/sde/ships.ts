import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql, inArray } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

import type { ShipFittingCapabilities, ShipInfo, ShipType, ShipMeta, ShipHull } from '@dtypes/layout_components'

export async function get_ship_fitting_capabilities(ship_name:string) {
    console.log(`Requesting: sde_db.get_ship_fitting_capabilities(${ship_name})`)

    const q = await sde_db.select({
        attributeName: schema.dgmAttributeTypes.attributeName,
        value: schema.dgmTypeAttributes.valueFloat,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.dgmTypeAttributes,
        eq(schema.invTypes.typeId, schema.dgmTypeAttributes.typeId),
    )
    .innerJoin(
        schema.dgmAttributeTypes,
        eq(schema.dgmTypeAttributes.attributeId, schema.dgmAttributeTypes.attributeId),
    )
    .where(
        and(
            eq(schema.invTypes.typeName, ship_name),
            or(
                and(
                    eq(schema.dgmAttributeTypes.published, '1'),
                    eq(schema.dgmAttributeTypes.categoryId, 1),
                ),
                eq(schema.dgmAttributeTypes.attributeName, 'maxSubSystems'),
            )
        )
    );

    const TRANSLATE = {
        'hiSlots': 'high_slots',
        'medSlots': 'med_slots',
        'lowSlots': 'low_slots',
        'upgradeSlotsLeft': 'rig_slots',
        'Subsystem Slots': 'subsystem_slots',
        'powerOutput': 'pg_output',
        'cpuOutput': 'cpu_output',
        'launcherSlotsLeft': 'launchers',
        'turretSlotsLeft': 'turrets',
    }
    
    let capabilities:ShipFittingCapabilities = {}
    q.map( (i) => {
        const translation = TRANSLATE[i?.attributeName ?? '']
        if (translation)
            capabilities[translation] = i.value
    })

    return capabilities
}

export async function get_ship_info(ship_id:number) {
    // console.log(`Requesting: sde_db.get_ship_info(${ship_id})`)

    const q = await sde_db.select({
        groupName: schema.invGroups.groupName,
        typeName: schema.invTypes.typeName,
        raceName: schema.chrRaces.raceName,
        metaGroupName: schema.invMetaGroups.metaGroupName,
    })
    .from(schema.invGroups)
    .innerJoin(
        schema.invTypes,
        eq(schema.invGroups.groupId, schema.invTypes.groupId),
    )
    .leftJoin(
        schema.chrRaces,
        eq(schema.invTypes.raceId, schema.chrRaces.raceId),
    )
    .leftJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeId, schema.invMetaTypes.typeId),
    )
    .leftJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupId, schema.invMetaGroups.metaGroupId),
    )
    .where(
        and(
            eq(schema.invTypes.typeId, ship_id),
            eq(schema.invGroups.categoryId, 6),
        )
    )
    .limit(1)

    if (q.length > 0) {
        return {
            name: q[0].typeName,
            type: q[0].groupName,
            race: q[0].raceName,
            meta: q[0].metaGroupName ?? 'Tech I',
        } as ShipInfo
    } else {
        return null
    }
}

export async function get_ships_type(ships_id:number[]) {
    // console.log(`Requesting: sde_db.get_ship_info(${ship_id})`)

    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
        groupName: schema.invGroups.groupName,
    })
    .from(schema.invGroups)
    .innerJoin(
        schema.invTypes,
        eq(schema.invGroups.groupId, schema.invTypes.groupId),
    )
    .where(
        inArray(schema.invTypes.typeId, ships_id),
    )

    return q.map(i => {
        return {
            ship_id: i.typeId,
            type: i.groupName,
        } as ShipType
    })
}

export async function get_ships_meta(ships_id:number[]) {
    // console.log(`Requesting: sde_db.get_ship_info(${ship_id})`)

    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
        metaGroupName: schema.invMetaGroups.metaGroupName,
    })
    .from(schema.invGroups)
    .innerJoin(
        schema.invTypes,
        eq(schema.invGroups.groupId, schema.invTypes.groupId),
    )
    .leftJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeId, schema.invMetaTypes.typeId),
    )
    .leftJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupId, schema.invMetaGroups.metaGroupId),
    )
    .where(
        inArray(schema.invTypes.typeId, ships_id),
    )

    return q.map(i => {
        return {
            ship_id: i.typeId,
            meta: i.metaGroupName ?? 'Tech I',
        } as ShipMeta
    })
}
/** Every published ship hull, by name: the choices for an off-doctrine pick. */
export async function get_ship_hulls():Promise<ShipHull[]> {
    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
        typeName: schema.invTypes.typeName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invGroups,
        eq(schema.invGroups.groupId, schema.invTypes.groupId),
    )
    .where(
        and(
            eq(schema.invGroups.categoryId, 6),
            eq(schema.invTypes.published, '1'),
        )
    )
    .orderBy(schema.invTypes.typeName)

    return q
        .filter(row => row.typeName)
        .map(row => ({ type_id: row.typeId, name: row.typeName as string }))
}

/** Every published ship group (Dreadnought, Logistics...), by name: a ship
 * target line can count a whole group. */
export async function get_ship_groups():Promise<ShipHull[]> {
    const q = await sde_db.select({
        groupId: schema.invGroups.groupId,
        groupName: schema.invGroups.groupName,
    })
    .from(schema.invGroups)
    .where(
        and(
            eq(schema.invGroups.categoryId, 6),
            eq(schema.invGroups.published, '1'),
        )
    )
    .orderBy(schema.invGroups.groupName)

    return q
        .filter(row => row.groupName)
        .map(row => ({ type_id: row.groupId, name: row.groupName as string }))
}

/** Every published ship's EVE group, by type id: tells the target line
 * editor which line already counts a hull through its group. */
export async function get_ship_hull_group_ids():Promise<Map<number, number>> {
    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
        groupId: schema.invTypes.groupId,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invGroups,
        eq(schema.invGroups.groupId, schema.invTypes.groupId),
    )
    .where(
        and(
            eq(schema.invGroups.categoryId, 6),
            eq(schema.invTypes.published, '1'),
        )
    )

    return new Map(q.map(row => [row.typeId, row.groupId as number]))
}
