import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

export async function get_item_id(item_name:string) {
    console.log(`Requesting: sde_db.get_item_id(${item_name})`)

    const q = await sde_db.select({
        typeId: schema.invTypes.typeID,
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
    console.log(`Requesting: sde_db.get_item_category(${item_id})`)

    const q = await sde_db.select({
        categoryName: schema.invCategories.categoryName
    })
    .from(schema.invTypes)
    .innerJoin(
        schema.invGroups,
        eq(schema.invTypes.groupID, schema.invGroups.groupID),
    )
    .innerJoin(
        schema.invCategories,
        eq(schema.invGroups.categoryID, schema.invCategories.categoryID),
    )
    .where(
        eq(schema.invTypes.typeID, item_id),
    )
    .limit(1);

    if (q.length > 0) {
        return q[0].categoryName
    } else {
        return null
    }
}