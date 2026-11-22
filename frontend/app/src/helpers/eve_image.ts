import type { EvEImageServiceSize } from '@dtypes/layout_components'

/**
 * Every images.evetech.net URL the site builds, in one place. The Picture
 * components (CharacterPicture, CorporationPicture, ItemPicture) and the
 * server-side helpers call these; markup never spells the host itself.
 *
 *     characters/{id}/portrait   get_player_icon(id, size)
 *     corporations/{id}/logo     get_corporation_logo(id, size)
 *     alliances/{id}/logo        get_alliance_logo(id, size)
 *     types/{id}/icon | render   get_type_icon / get_type_render / get_item_icon
 *     types/{id}/bp | bpc        get_bpc_icon
 *
 * Each takes a size in px. Portraits and logos are square at any size; type
 * icons are for sizes up to 64, renders above.
 */
const IMAGE_SERVER = 'https://images.evetech.net'

type ImageKind = 'characters/portrait' | 'corporations/logo' | 'alliances/logo' | 'types/icon' | 'types/render' | 'types/bp' | 'types/bpc'

const image_url = (kind:ImageKind, id:number, size:number):string => {
    const [collection, variant] = kind.split('/')
    return `${IMAGE_SERVER}/${collection}/${id}/${variant}?size=${size}`
}

/** A ship or item icon (up to 64px) or its render (above 64px). */
export const get_item_icon = (id:number, size:EvEImageServiceSize = 64):string => {
    return image_url(size <= 64 ? 'types/icon' : 'types/render', id, size)
}

/** The flat type icon at any size, for lists that always show icons. */
export const get_type_icon = (id:number, size:number = 64):string => image_url('types/icon', id, size)

/** The 3D render of a type, for large pictures and share images. */
export const get_type_render = (id:number, size:number = 512):string => image_url('types/render', id, size)

export const get_bpc_icon = (id:number, is_copy:boolean = false, size:EvEImageServiceSize = 64):string => {
    return image_url(is_copy ? 'types/bpc' : 'types/bp', id, size)
}

export const get_player_icon = (id:number, size:number = 64):string => {
    return image_url('characters/portrait', id, size)
}

export const get_alliance_logo = (id:number, size:number = 32):string => {
    return image_url('alliances/logo', id, size)
}

export const get_corporation_logo = (id:number, size:number = 32):string => {
    return image_url('corporations/logo', id, size)
}

// Alliances from 2010 on start here. Older ones share the range with
// corporations, so the API's `kind` decides whenever it is sent.
const FIRST_ALLIANCE_ID = 99000000

/** The logo for a killmail group: an alliance, or a corporation outside one. */
export const get_group_logo = (id:number, size:number = 32, kind?:string | null):string => {
    const alliance = kind ? kind === 'alliance' : id >= FIRST_ALLIANCE_ID
    return alliance ? get_alliance_logo(id, size) : get_corporation_logo(id, size)
}
