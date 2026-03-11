import modules_icon_lookup from '@json/hosted/modules-icon-lookup.json';
import type { EvEImageServiceSize } from '@dtypes/layout_components'

export const get_item_icon = (id:number, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${id}/${size <= 64 ? 'icon' : 'render'}?size=${size}`;
}

export const get_bpc_icon = (id:number, is_copy:boolean = false, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${id}/${is_copy ? 'bpc' : 'bp'}?size=${size}`;
}

export const get_item_icon_by_name = (name:string, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${modules_icon_lookup[name] ?? 0}/${size == 64 ? 'icon' : 'render'}?size=${size}`;
}

export const get_player_icon = (id:number, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/characters/${id}/portrait?size=${size}`;
}

export const get_alliance_logo = (id:number, size:EvEImageServiceSize = 32):string => {
    return `https://images.evetech.net/alliances/${id}/logo?size=${size}`;
}

export const get_corporation_logo = (id:number, size:EvEImageServiceSize = 32):string => {
    return `https://images.evetech.net/corporations/${id}/logo?size=${size}`;
}

export const PLANET_THUMBS = {
    'temperate': '/images/temperate_planet.webp',
    'gas': '/images/gas_planet.webp',
    'ice': '/images/ice_planet.webp',
    'barren': '/images/barren_planet.webp',
    'lava': '/images/lava_planet.webp',
    'plasma': '/images/plasma_planet.webp',
    'storm': '/images/storm_planet.webp',
    'oceanic': '/images/oceanic_planet.webp',
}