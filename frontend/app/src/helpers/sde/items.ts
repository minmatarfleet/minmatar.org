import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

export async function get_item_id(module_name:string) {
    const q = await db.select({
        id: schema.invTypes.typeId,
    })
    .from(schema.invTypes)
    .where(
        eq(schema.invTypes.typeName, module_name),
    );
    
    if (q.length > 0) {
        return q[0].id
    } else {
        return null
    }
}