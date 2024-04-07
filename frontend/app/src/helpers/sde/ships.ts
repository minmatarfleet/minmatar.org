import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

import type { ShipFittingCapabilities } from '@dtypes/layout_components'

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