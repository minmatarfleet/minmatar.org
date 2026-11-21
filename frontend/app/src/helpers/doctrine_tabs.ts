import type { Stagings } from '@dtypes/api.minmatar.org'

export type DoctrineTabId = 'home' | 'deployed'

export interface DoctrineTabLocations {
    id:           DoctrineTabId;
    /** Short names of the locations the tab covers, for its label. */
    names:        string[];
    location_ids: number[];
}

/**
 * The doctrine tabs: Home and Deployed. Empty when nothing is deployed (or no
 * home staging is set), so the page keeps its single-location layout.
 */
export function doctrine_tabs(stagings: Stagings): DoctrineTabLocations[] {
    if (!stagings.home || stagings.deployments.length === 0)
        return []

    return [
        {
            id: 'home',
            names: [stagings.home.short_name],
            location_ids: [stagings.home.location_id],
        },
        {
            id: 'deployed',
            names: stagings.deployments.map((location) => location.short_name),
            location_ids: stagings.deployments.map((location) => location.location_id),
        },
    ]
}

/** Doctrines staged at any of the locations. */
export function doctrines_at<Doctrine extends { location_ids?: number[] }>(
    doctrines: Doctrine[],
    location_ids: number[],
): Doctrine[] {
    return doctrines.filter((doctrine) =>
        (doctrine.location_ids ?? []).some((location_id) => location_ids.includes(location_id))
    )
}

/** The tab an old `?location_id=` link belongs to; Home when it matches neither. */
export function tab_for_location(tabs: DoctrineTabLocations[], location_id: number): DoctrineTabId {
    const deployed = tabs.find((tab) => tab.id === 'deployed')
    return deployed?.location_ids.includes(location_id) ? 'deployed' : 'home'
}
