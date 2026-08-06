import type { Fitting } from '@dtypes/api.minmatar.org'
import type { CapitalHull } from './types'

export function fittingsForShipId(ship_id: number, library: Fitting[]): Fitting[] {
    const for_ship = library.filter((fit) => fit.ship_id === ship_id)
    const capitals = for_ship.filter((fit) => fit.tags?.includes('capitals'))
    return capitals.length > 0 ? capitals : for_ship
}

export function fittingsForHull(hull: CapitalHull, library: Fitting[]): Fitting[] {
    return fittingsForShipId(hull.shipId, library)
}
