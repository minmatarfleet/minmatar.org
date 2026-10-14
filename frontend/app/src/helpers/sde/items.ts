import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql, inArray } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

export async function get_item_id(item_name:string) {
    console.log(`Requesting: sde_db.get_item_id(${item_name})`)

    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
    })
    .from(schema.invTypes)
    .where(
        eq(schema.invTypes.typeName, item_name),
    )
    .limit(1);
    
    if (q.length > 0) {
        return q[0].typeId
    } else {
        return null
    }
}

export async function get_item_name(type_id: number) {
    const q = await sde_db.select({
        typeName: schema.invTypes.typeName,
    })
    .from(schema.invTypes)
    .where(
        eq(schema.invTypes.typeId, type_id),
    )
    .limit(1)

    if (q.length > 0) {
        return q[0].typeName
    }
    return null
}

export async function get_item_category(item_id:number) {
    console.log(`Requesting: sde_db.get_item_category(${item_id})`)

    const q = await sde_db.select({
        categoryName: schema.invCategories.categoryName
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invGroups,
        eq(schema.invTypes.groupId, schema.invGroups.groupId),
    )
    .innerJoin(
        schema.invCategories,
        eq(schema.invGroups.categoryId, schema.invCategories.categoryId),
    )
    .where(
        eq(schema.invTypes.typeId, item_id),
    )
    .limit(1);

    if (q.length > 0) {
        return q[0].categoryName
    } else {
        return null
    }
}

/** Type names for a batch of ids in one query; ids the SDE lacks are simply absent. */
export async function get_type_names(type_ids:number[]):Promise<Map<number, string>> {
    const ids = [ ...new Set(type_ids.filter(id => Number.isFinite(id) && id > 0)) ]
    if (ids.length === 0) return new Map()

    const q = await sde_db.select({
        typeId: schema.invTypes.typeId,
        typeName: schema.invTypes.typeName,
    })
    .from(schema.invTypes)
    .where(
        inArray(schema.invTypes.typeId, ids),
    )

    return new Map(q.map(row => [ row.typeId as number, row.typeName as string ]))
}
