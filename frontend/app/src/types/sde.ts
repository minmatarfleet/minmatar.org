// View models for static EVE data (the SDE snapshot) shown by the components in
// src/components/blocks/sde/. The query helpers in src/helpers/sde/search.ts
// return these shapes, and rust/fixtures/sde.json holds real rows of them.

/** Slot layout of a ship hull, from its dogma attributes. */
export interface ShipSlotCounts {
    high:       number;
    mid:        number;
    low:        number;
    rig:        number;
    /** Strategic cruisers only; 0 for every other hull. */
    subsystem:  number;
    turrets?:   number;
    launchers?: number;
}

/** An inventory type (ship, module, charge, material...) with its group, category and meta group. */
export interface SdeType {
    type_id:            number;
    type_name:          string;
    group_id:           number;
    group_name:         string;
    category_id:        number;
    category_name:      string;
    /** null when the SDE has no meta group for the type (most non-modules). */
    meta_group_id:      number | null;
    meta_group_name:    string | null;
    /** Ships only. */
    slots?:             ShipSlotCounts;
}

/** A solar system with its constellation and region. */
export interface SdeSolarSystem {
    system_id:          number;
    system_name:        string;
    /** The raw SDE value; display it with `display_security()`. */
    security:           number;
    sun_type_id:        number | null;
    constellation_id:   number;
    constellation_name: string;
    region_id:          number;
    region_name:        string;
}

export type SecurityBand = 'high' | 'low' | 'null' | 'wormhole'
