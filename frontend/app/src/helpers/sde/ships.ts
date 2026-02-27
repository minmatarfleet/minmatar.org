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
        eq(schema.invTypes.typeID, schema.dgmTypeAttributes.typeID),
    )
    .innerJoin(
        schema.dgmAttributeTypes,
        eq(schema.dgmTypeAttributes.attributeID, schema.dgmAttributeTypes.attributeID),
    )
    .where(
        and(
            eq(schema.invTypes.typeName, ship_name),
            or(
                and(
                    eq(schema.dgmAttributeTypes.published, '1'),
                    eq(schema.dgmAttributeTypes.categoryID, 1),
                ),
                eq(schema.dgmAttributeTypes.attributeName, 'Subsystem Slots'),
            )
        )
    );

    const TRANSLATE = {
        'High Slots': 'high_slots',
        'Medium Slots': 'med_slots',
        'Low Slots': 'low_slots',
        'Rig Slots': 'rig_slots',
        'Subsystem Slots': 'subsystem_slots',
        'Powergrid Output': 'pg_output',
        'CPU Output': 'cpu_output',
        'Launcher Hardpoints': 'launchers',
        'Turret Hardpoints': 'turrets',
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
        eq(schema.invGroups.groupID, schema.invTypes.groupID),
    )
    .leftJoin(
        schema.chrRaces,
        eq(schema.invTypes.raceID, schema.chrRaces.raceID),
    )
    .leftJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeID, schema.invMetaTypes.typeID),
    )
    .leftJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupID, schema.invMetaGroups.metaGroupID),
    )
    .where(
        and(
            eq(schema.invTypes.typeID, ship_id),
            eq(schema.invGroups.categoryID, 6),
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
        eq(schema.invTypes.graphicID, schema.eveGraphics.graphicID),
    )
    .where(
        eq(schema.invTypes.typeID, ship_id)
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
        typeID: schema.invTypes.typeID,
        groupName: schema.invGroups.groupName,
    })
    .from(schema.invGroups)
    .innerJoin(
        schema.invTypes,
        eq(schema.invGroups.groupID, schema.invTypes.groupID),
    )
    .where(
        inArray(schema.invTypes.typeID, ships_id),
    )

    return q.map(i => {
        return {
            ship_id: i.typeID,
            type: i.groupName,
        } as ShipType
    })
}

export async function get_ships_meta(ships_id:number[]) {
    // console.log(`Requesting: sde_db.get_ship_info(${ship_id})`)

    const q = await sde_db.select({
        typeID: schema.invTypes.typeID,
        metaGroupName: schema.invMetaGroups.metaGroupName,
    })
    .from(schema.invGroups)
    .innerJoin(
        schema.invTypes,
        eq(schema.invGroups.groupID, schema.invTypes.groupID),
    )
    .leftJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeID, schema.invMetaTypes.typeID),
    )
    .leftJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupID, schema.invMetaGroups.metaGroupID),
    )
    .where(
        inArray(schema.invTypes.typeID, ships_id),
    )

    return q.map(i => {
        return {
            ship_id: i.typeID,
            meta: i.metaGroupName ?? 'Tech I',
        } as ShipMeta
    })
}