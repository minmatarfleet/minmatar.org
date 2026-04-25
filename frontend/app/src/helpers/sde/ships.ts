import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql, inArray } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

import type { ShipFittingCapabilities, ShipInfo, ShipDNA, ShipType, ShipMeta } from '@dtypes/layout_components'

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

export async function get_ship_graphics(ship_id:number) {
    console.log(`Requesting: sde_db.get_ship_dna(${ship_id})`)
    
    const q = await sde_db.select({
        sofFactionName: schema.eveGraphics.sofFactionName,
        sofRaceName: schema.eveGraphics.sofRaceName,
        sofHullName: schema.eveGraphics.sofHullName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.eveGraphics,
        eq(schema.invTypes.graphicId, schema.eveGraphics.graphicId),
    )
    .where(
        eq(schema.invTypes.typeId, ship_id)
    )
    .limit(1)

    if (q.length > 0) {
        return {
            model: q[0].sofHullName,
            skin: q[0].sofFactionName,
            race: q[0].sofRaceName,
        } as ShipDNA
    } else
        return null
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