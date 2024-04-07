import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

import type { Module } from '@dtypes/layout_components'

export async function get_module_props(module_name:string) {
    console.log(`Requesting: db.get_module_props(${module_name})`)

    const q = await db.select({
        typeId: schema.invTypes.typeId,
        moduleName: schema.invTypes.typeName,
        metaName: schema.invMetaGroups.metaGroupName,
        slotName: schema.dgmEffects.displayName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invMetaTypes,
        eq(schema.invTypes.typeId, schema.invMetaTypes.typeId),
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
            slot_name: q[0].slotName
        } as Module
    } else {
        return null
    }
}