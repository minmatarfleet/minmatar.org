import { db } from '@helpers/db';
import { eq, and, or, sql } from 'drizzle-orm';
import * as schema from '@/models/schema.ts';

export async function get_system_id(solar_system:string) {
    console.log(`Requesting: db.get_system_id(${solar_system})`)

    const q = await db.select({
        solarSystemId: schema.mapSolarSystems.solarSystemId,
    })
    .from(schema.mapSolarSystems)
    .where(
        eq(schema.mapSolarSystems.solarSystemName, solar_system),
    )
    .limit(1);
    
    if (q.length > 0) {
        return q[0].solarSystemId
    } else {
        return null
    }
}

export async function get_system_sun_type_id(solar_system_id:number) {
    console.log(`Requesting: db.get_system_sun_type(${solar_system_id})`)

    const q = await db.select({
        sunTypeId: schema.mapSolarSystems.sunTypeId,
    })
    .from(schema.mapSolarSystems)
    .where(
        eq(schema.mapSolarSystems.solarSystemId, solar_system_id),
    )
    .limit(1);
    
    if (q.length > 0) {
        return q[0].sunTypeId
    } else {
        return null
    }
}