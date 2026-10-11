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

export function infer_fit_match(notes?: string): string | undefined {
    if (!notes) {
        return undefined
    }
    if (/\bbuffer\b|\bpassive\b/i.test(notes)) {
        return 'Buffer'
    }
    if (/\bactive\b/i.test(notes)) {
        return 'Active'
    }
    return undefined
}

function pick_fitting_by_name_match(fittings: Fitting[], match: string): Fitting | undefined {
    const needle = match.trim().toLowerCase()
    if (!needle) {
        return undefined
    }
    const hits = fittings.filter((fit) => fit.name.toLowerCase().includes(needle))
    if (hits.length === 0) {
        return undefined
    }
    const without_geno = hits.filter((fit) => !/\bgeno\b/i.test(fit.name))
    const pool = without_geno.length > 0 ? without_geno : hits
    return [...pool].sort((left, right) => {
        const by_length = left.name.length - right.name.length
        if (by_length !== 0) {
            return by_length
        }
        return left.id - right.id
    })[0]
}

export function primary_fitting(
    fittings: Fitting[],
    options?: { fit_match?: string; notes?: string },
): Fitting | null {
    if (fittings.length === 0) {
        return null
    }
    const match = options?.fit_match?.trim() || infer_fit_match(options?.notes)
    const matched = match ? pick_fitting_by_name_match(fittings, match) : undefined
    return matched ?? fittings[0]
}

export function primary_fitting_for_ship(
    ship_id: number,
    library: Fitting[],
    options?: { fit_match?: string; notes?: string },
): Fitting | null {
    return primary_fitting(fittingsForShipId(ship_id, library), options)
}
