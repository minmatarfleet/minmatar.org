import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

import type { Module } from '@dtypes/layout_components'

export async function get_module_props(module_name:string) {
    console.log(`Requesting: db.get_module_props(${module_name})`)

    const q = await db.select({
        typeId: schema.invTypes.typeId,
        moduleName: schema.invTypes.typeName,
        groupName: schema.invGroups.groupName,
        metaName: schema.invMetaGroups.metaGroupName,
        slotName: schema.dgmEffects.displayName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeId, schema.invMetaTypes.typeId),
    )
    .innerJoin(
        schema.invGroups,
        eq(schema.invTypes.groupId, schema.invGroups.groupId),
    )
    .innerJoin(
        schema.invMetaGroups,
        eq(schema.invMetaTypes.metaGroupId, schema.invMetaGroups.metaGroupId),
    )
    .innerJoin(
        schema.dgmTypeEffects,
        eq(schema.invTypes.typeId, schema.dgmTypeEffects.typeId),
    )
    .innerJoin(
        schema.dgmEffects,
        eq(schema.dgmTypeEffects.effectId, schema.dgmEffects.effectId),
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
    const q = await db.select({
        typeId: schema.dgmTypeAttributes.valueFloat,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.dgmTypeAttributes,
        eq(schema.invTypes.typeId, schema.dgmTypeAttributes.typeId)
    )
    .innerJoin(
        schema.dgmAttributeTypes,
        eq(schema.dgmTypeAttributes.attributeId, schema.dgmAttributeTypes.attributeId)
    )
    .where(
        and(
            eq(schema.invTypes.typeId, weapon_id),
            eq(schema.dgmAttributeTypes.attributeName, 'Charge size'),
        )
    )
}

export async function get_module_model(module_id:number) {
    const q = await db.select({
        graphicFile: schema.eveGraphics.graphicFile,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.dgmTypeAttributes,
        eq(schema.invTypes.typeId, schema.dgmTypeAttributes.typeId)
    )
    .innerJoin(
        schema.eveGraphics,
        eq(schema.invTypes.graphicId, schema.eveGraphics.graphicId)
    )
    .where(
        and(
            eq(schema.invTypes.typeId, module_id),
        )
    )
    .limit(1)

    if (q.length > 0)
        return q[0].graphicFile
    else
        return null
}