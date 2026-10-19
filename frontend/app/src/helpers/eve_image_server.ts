import type { EvEImageServiceSize } from '@dtypes/layout_components'

export const get_item_icon = (id:number, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${id}/${size <= 64 ? 'icon' : 'render'}?size=${size}`;
}

export const get_bpc_icon = (id:number, is_copy:boolean = false, size:EvEImageServiceSize = 64):string => {
    return `https://images.evetech.net/types/${id}/${is_copy ? 'bpc' : 'bp'}?size=${size}`;
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

// Alliances from 2010 on start here. Older ones share the range with
// corporations, so the API's `kind` decides whenever it is sent.
const FIRST_ALLIANCE_ID = 99000000

/** The logo for a killmail group: an alliance, or a corporation outside one. */
export const get_group_logo = (id:number, size:EvEImageServiceSize = 32, kind?:string | null):string => {
    const alliance = kind ? kind === 'alliance' : id >= FIRST_ALLIANCE_ID
    return alliance ? get_alliance_logo(id, size) : get_corporation_logo(id, size)
}
