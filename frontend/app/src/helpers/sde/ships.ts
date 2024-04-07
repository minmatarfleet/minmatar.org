import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

import type { ShipFittingCapabilities, ShipInfo } from '@dtypes/layout_components'

export async function get_ship_fitting_capabilities(ship_name:string) {
    console.log(`Requesting: db.get_ship_fitting_capabilities(${ship_name})`)

    const q = await db.select({
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
        if (TRANSLATE[i.attributeName]) {
            capabilities[TRANSLATE[i.attributeName]] = i.value
        }
    })

    return capabilities
}

export async function get_ship_info(ship_id:number) {
    const q = await db.select({
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
    .innerJoin(
        schema.chrRaces,
        eq(schema.invTypes.raceId, schema.chrRaces.raceId),
    )
    .innerJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeId, schema.invMetaTypes.typeId),
    )
    .innerJoin(
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
            meta: q[0].metaGroupName,
        } as ShipInfo
    } else {
        return null
    }
}