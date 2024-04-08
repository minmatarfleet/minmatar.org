import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

export async function get_item_id(item_name:string) {
    console.log(`Requesting: db.get_item_id(${item_name})`)

    const q = await db.select({
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

export async function get_item_category(item_id:number) {
    console.log(`Requesting: db.get_item_category(${item_id})`)

    const q = await db.select({
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