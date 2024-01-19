import modules_icon_lookup from '@json/hosted/modules-icon-lookup.json';
import type { EvEImageServiceSize } from '@dtypes/LayoutComponents'

export const get_item_icon = (id:number, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${id}/${size <= 64 ? 'icon' : 'render'}?size=${size}`;
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