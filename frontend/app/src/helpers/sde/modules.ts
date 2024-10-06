import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

import type { Module } from '@dtypes/layout_components'

export async function get_module_props(module_name:string) {
    console.log(`Requesting: sde_db.get_module_props(${module_name})`)

    const q = await sde_db.select({
        typeId: schema.invTypes.typeID,
        moduleName: schema.invTypes.typeName,
        groupName: schema.invGroups.groupName,
        metaName: schema.invMetaGroups.metaGroupName,
        slotName: schema.dgmEffects.displayName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeID, schema.invMetaTypes.typeID),
    )
    .innerJoin(
        schema.invGroups,
        eq(schema.invTypes.groupID, schema.invGroups.groupID),
    )
    .innerJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupID, schema.invMetaGroups.metaGroupID),
    )
    .innerJoin(
        schema.dgmTypeEffects,
        eq(schema.invTypes.typeID, schema.dgmTypeEffects.typeID),
    )
    .innerJoin(
        schema.dgmEffects,
        eq(schema.dgmTypeEffects.effectID, schema.dgmEffects.effectID),
    )
    .where(
        and(
            eq(schema.invTypes.typeName, module_name),
            or(
                eq(schema.dgmEffects.effectName, 'loPower'),
                eq(schema.dgmEffects.effectName, 'hiPower'),
                eq(schema.dgmEffects.effectName, 'medPower'),
                eq(schema.dgmEffects.effectName, 'rigSlot'),
                eq(schema.dgmEffects.effectName, 'subSystem'),
            ),
        )
    )
    .limit(1);
    
    if (q.length > 0) {
        return {
            id: q[0].typeId,
            name: q[0].moduleName,
            meta_name: q[0].metaName,
            module_type: q[0].groupName,
            slot_name: q[0].slotName
        } as Module
    } else {
        return null
    }
}

export async function get_weapon_charges_type(weapon_id:number) {
    const q = await sde_db.select({
        typeId: schema.dgmTypeAttributes.valueFloat,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.dgmTypeAttributes,
        eq(schema.invTypes.typeID, schema.dgmTypeAttributes.typeID)
    )
    .innerJoin(
        schema.dgmAttributeTypes,
        eq(schema.dgmTypeAttributes.attributeID, schema.dgmAttributeTypes.attributeID)
    )
    .where(
        and(
            eq(schema.invTypes.typeID, weapon_id),
            eq(schema.dgmAttributeTypes.attributeName, 'Charge size'),
        )
    )
}

export async function get_module_model(module_id:number) {
    const q = await sde_db.select({
        graphicFile: schema.eveGraphics.graphicFile,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.dgmTypeAttributes,
        eq(schema.invTypes.typeID, schema.dgmTypeAttributes.typeID)
    )
    .innerJoin(
        schema.eveGraphics,
        eq(schema.invTypes.graphicID, schema.eveGraphics.graphicID)
    )
    .where(
        and(
            eq(schema.invTypes.typeID, module_id),
        )
    )
    .limit(1)

    if (q.length > 0)
        return q[0].graphicFile
    else
        return null
}