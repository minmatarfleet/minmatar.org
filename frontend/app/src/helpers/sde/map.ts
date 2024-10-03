import { sde_db } from '@helpers/sde_db';
import { eq, and, or, sql, like, inArray } from 'drizzle-orm';
import * as schema from '@/models/sde/schema.ts';

import type { RegionBasic, MoonBasic, PlanetBasic } from '@dtypes/layout_components'

export async function get_system_id(solar_system:string) {
    console.log(`Requesting: sde_db.get_system_id(${solar_system})`)

    const q = await sde_db.select({
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

export interface sde_system {
    regionId:           number;
    regionName:         string;
    constellationId:    number;
    constellationName:  string;
    solarSystemName:    string;
    solarSystemId:      number;
    sunTypeId:          number;
    security:           number;
    x?:                 number;
    y?:                 number;
    z?:                 number;
}

export async function find_systems_by_name(find:string) {
    console.log(`Requesting: sde_db.find_systems_by_name(${find})`)

    const q = await sde_db.select({
        solarSystemId: schema.mapSolarSystems.solarSystemId,
        solarSystemName: schema.mapSolarSystems.solarSystemName,
        sunTypeId: schema.mapSolarSystems.sunTypeId,
        security: schema.mapSolarSystems.security,
        regionId: schema.mapSolarSystems.regionId,
        regionName: schema.mapRegions.regionName,
        constellationId: schema.mapSolarSystems.constellationId,
        constellationName: schema.mapConstellations.constellationName,
    })
    .from(schema.mapSolarSystems)
    .innerJoin(
        schema.mapRegions,
        eq(schema.mapSolarSystems.regionId, schema.mapRegions.regionId),
    )
    .innerJoin(
        schema.mapConstellations,
        eq(schema.mapSolarSystems.constellationId, schema.mapConstellations.constellationId),
    )
    .where(
        like(schema.mapSolarSystems.solarSystemName, `%${find}%`),
    );
    
    return q as sde_system[]
}

export interface sde_filtered_system {
    system_id:              number;
    system_name:            string;
    sun_type_id:            number;
    security:               number;
    region_id:              number;
    region_name:            string;
    constellation_id:       number;
    constellation_name:     string;
}

export async function filter_systems_by_name(find:string) {
    console.log(`Requesting: sde_db.find_systems_by_name(${find})`)

    const q = await sde_db.select({
        system_id: schema.mapSolarSystems.solarSystemId,
        system_name: schema.mapSolarSystems.solarSystemName,
        sun_type_id: schema.mapSolarSystems.sunTypeId,
        security: schema.mapSolarSystems.security,
        region_id: schema.mapSolarSystems.regionId,
        region_name: schema.mapRegions.regionName,
        constellation_id: schema.mapSolarSystems.constellationId,
        constellation_name: schema.mapConstellations.constellationName,
    })
    .from(schema.mapSolarSystems)
    .innerJoin(
        schema.mapRegions,
        eq(schema.mapSolarSystems.regionId, schema.mapRegions.regionId),
    )
    .innerJoin(
        schema.mapConstellations,
        eq(schema.mapSolarSystems.constellationId, schema.mapConstellations.constellationId),
    )
    .where(
        like(schema.mapSolarSystems.solarSystemName, `${find}%`),
    );
    
    return q as sde_filtered_system[]
}

export async function find_systems_moons(systems_ids:number[]) {
    console.log(`Requesting: sde_db.find_system_moons(${systems_ids.join(',')})`)

    const SDE_MOONS_GROUP_ID = 8

    const q = await sde_db.select({
        id: schema.invItems.itemId,
        name: schema.invUniqueNames.itemName,
        system_id: schema.mapSolarSystems.solarSystemId,
    })
    .from(schema.invItems)
    .innerJoin(
        schema.mapSolarSystems,
        eq(schema.invItems.locationId, schema.mapSolarSystems.solarSystemId),
    )
    .innerJoin(
        schema.invUniqueNames,
        eq(schema.invUniqueNames.itemId, schema.invItems.itemId),
    )
    .where(
        and(
            eq(schema.invUniqueNames.groupId, SDE_MOONS_GROUP_ID),
            inArray(schema.mapSolarSystems.solarSystemId, systems_ids)
        )
    );
    
    return q as MoonBasic[]
}

export async function find_system_moons_fast(system_name:string) {
    console.log(`Requesting: sde_db.find_system_moons(${system_name})`)

    const SDE_MOONS_GROUP_ID = 8

    const q = await sde_db.select({
        id: schema.invUniqueNames.itemId,
        name: schema.invUniqueNames.itemName,
    })
    .from(schema.invUniqueNames)
    .where(
        and(
            eq(schema.invUniqueNames.groupId, SDE_MOONS_GROUP_ID),
            like(schema.invUniqueNames.itemName, `${system_name}%`)
        )
    );
    
    return q as MoonBasic[]
}

export async function find_system_planets(system_id:number) {
    console.log(`Requesting: sde_db.find_system_planets(${system_id})`)

    const SDE_PLANETS_GROUP_ID = 7

    const q = await sde_db.select({
        id: schema.invItems.itemId,
        name: schema.invUniqueNames.itemName,
        type_id: schema.invItems.typeId,
    })
    .from(schema.invItems)
    .innerJoin(
        schema.invUniqueNames,
        eq(schema.invUniqueNames.itemId, schema.invItems.itemId),
    )
    .innerJoin(
        schema.mapSolarSystems,
        eq(schema.invItems.locationId, schema.mapSolarSystems.solarSystemId),
    )
    .where(
        and(
            eq(schema.invUniqueNames.groupId, SDE_PLANETS_GROUP_ID),
            eq(schema.mapSolarSystems.solarSystemId, system_id)
        )
    );
    
    return q as PlanetBasic[]
}

export async function get_system_sun_type_id(solar_system_id:number) {
    console.log(`Requesting: sde_db.get_system_sun_type(${solar_system_id})`)

    const q = await sde_db.select({
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

export async function get_system_sun_type_id_by_name(solar_system_name:string) {
    console.log(`Requesting: sde_db.get_system_sun_type_id_by_name(${solar_system_name})`)

    const q = await sde_db.select({
        sunTypeId: schema.mapSolarSystems.sunTypeId,
    })
    .from(schema.mapSolarSystems)
    .where(
        eq(schema.mapSolarSystems.solarSystemName, solar_system_name),
    )
    .limit(1);
    
    if (q.length > 0) {
        return q[0].sunTypeId
    } else {
        return null
    }
}

export async function get_systems_coordinates() {
    console.log(`Requesting: sde_db.get_systems_coordinates()`)

    const q = await sde_db.select({
        regionId: schema.mapSolarSystems.regionId,
        regionName: schema.mapRegions.regionName,
        constellationId: schema.mapSolarSystems.constellationId,
        constellationName: schema.mapConstellations.constellationName,
        solarSystemName: schema.mapSolarSystems.solarSystemName,
        solarSystemId: schema.mapSolarSystems.solarSystemId,
        sunTypeId: schema.mapSolarSystems.sunTypeId,
        security: schema.mapSolarSystems.security,
        x: schema.mapSolarSystems.x,
        y: schema.mapSolarSystems.y,
        z: schema.mapSolarSystems.z,
    })
    .from(schema.mapSolarSystems)
    .innerJoin(
        schema.mapRegions,
        eq(schema.mapSolarSystems.regionId, schema.mapRegions.regionId),
    )
    .innerJoin(
        schema.mapConstellations,
        eq(schema.mapSolarSystems.constellationId, schema.mapConstellations.constellationId),
    )
    
    return q as sde_system[]
}

export async function get_regions() {
    console.log(`Requesting: sde_db.get_regions()`)

    const q = await sde_db.select({
        id: schema.mapRegions.regionId,
        name: schema.mapRegions.regionName,
    })
    .from(schema.mapRegions);
    
    return q as RegionBasic[]
}

import type { ConstellationBasic } from '@dtypes/layout_components'

export async function get_constellations() {
    console.log(`Requesting: sde_db.get_regions()`)

    const q = await sde_db.select({
        id: schema.mapConstellations.constellationId,
        name: schema.mapConstellations.constellationName,
    })
    .from(schema.mapRegions);
    
    return q as ConstellationBasic[]
}