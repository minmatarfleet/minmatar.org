import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

export async function get_item_id(module_name:string) {
    console.log(`Requesting: db.get_item_id(${module_name})`)

    const q = await db.select({
        typeId: schema.invTypes.typeId,
    })
    .from(schema.invTypes)
    .where(
        eq(schema.invTypes.typeName, module_name),
    )
    .limit(1);
    
    if (q.length > 0) {
        return q[0].typeId
    } else {
        return null
    }
}