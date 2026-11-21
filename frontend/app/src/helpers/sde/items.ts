import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql, inArray } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';
import { alias } from 'drizzle-orm/sqlite-core';

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

export interface BuildableTypeMatch {
    type_id: number
    type_name: string
}

/**
 * Published items that a published blueprint manufactures, matched by name.
 * Names that start with the query come first, then shorter names.
 */
export async function search_buildable_types(query:string, limit = 20):Promise<BuildableTypeMatch[]> {
    const needle = query.replace(/[%_]/g, '').trim()
    if (needle.length < 2) return []

    const blueprint = alias(schema.invTypes, 'blueprint')

    const q = await sde_db.selectDistinct({
        typeId: schema.invTypes.typeId,
        typeName: schema.invTypes.typeName,
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.industryActivityProducts,
        and(
            eq(schema.industryActivityProducts.productTypeId, schema.invTypes.typeId),
            eq(schema.industryActivityProducts.activityId, 1),
        ),
    )
    .innerJoin(blueprint, eq(blueprint.typeId, schema.industryActivityProducts.typeId))
    .where(
        and(
            sql`${schema.invTypes.published} = 1`,
            sql`${blueprint.published} = 1`,
            sql`${schema.invTypes.typeName} LIKE ${`%${needle}%`}`,
        ),
    )
    .orderBy(
        sql`CASE WHEN ${schema.invTypes.typeName} LIKE ${`${needle}%`} THEN 0 ELSE 1 END`,
        sql`length(${schema.invTypes.typeName})`,
        schema.invTypes.typeName,
    )
    .limit(limit)

    return q.map(row => ({ type_id: row.typeId as number, type_name: row.typeName as string }))
}
