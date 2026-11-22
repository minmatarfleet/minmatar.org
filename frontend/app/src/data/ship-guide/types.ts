/** Types shared by every ship guide (navy frigates, navy destroyers, FW cruisers) and the ship-guide components. */
import type { KnownFittingKey } from '@dtypes/api.minmatar.org'

export type MatchupRating = '++' | '+' | '=' | '-' | '--' | '?'

export type GuideFitting = {
    id: string
    knownKey?: KnownFittingKey | null
    fittingId: number
    shipId: number
    shipGuideId: string
    name: string
    description: string
    eftFormat: string
}

export type ShipProseSection = {
    id: string
    title: string
    paragraphs: string[]
    bullets?: string[]
}

export type MatchupVerdict = 'favoured' | 'unfavoured' | 'even' | 'bail' | 'skill' | 'unknown'

export type MatchupEntry = {
    opponent: string
    advice: string
    verdict?: MatchupVerdict
    load?: string
}

export type MatchupGroup = {
    title: string
    fitContext?: string
    entries: MatchupEntry[]
}

export type ShipBonus = {
    label: string
    value: string
}

export type ShipGuide = {
    id: string
    name: string
    shortName: string
    faction: string
    shipId: number
    tagline: string
    bonuses: ShipBonus[]
    roleBonus: string
    sections: ShipProseSection[]
    matchups: MatchupGroup[]
}

export type GlossaryEntry = {
    term: string
    definition: string
}

export type GuideSection = {
    id: string
    title: string
    shortTitle?: string
    group?: string
}

export type MatchupChart = {
    id: string
    title: string
    rowLabel: string
    columnLabel: string
    rows: string[]
    columns: string[]
    matrix: MatchupRating[][]
}

export type ResolvedOpponentShip = {
    shipId: number
    shipName: string
}

/** Maps a free-text matchup opponent label to a hull for its icon. */
export type OpponentShipResolver = (
    opponent: string,
    selfShip?: ResolvedOpponentShip,
) => ResolvedOpponentShip | null

export type GuideResourceLink = {
    title: string
    href: string
    note: string
}

export type GuideMatchupLegendItem = {
    rating: MatchupRating
    label: string
    description: string
}

/** A run of the Additional Resources lead-in: plain text or an external link. */
export type ResourcesIntroPart = string | { href: string; label: string }

/** Everything the `ShipGuide` block renders: one config per guide, assembled in `src/data/<guide>/guide.ts`. */
export type ShipGuideConfig = {
    /** Prefix for heading and copy-button ids, e.g. `nfg`. */
    id_prefix: string
    /** Hull class shown in each ship's kicker, e.g. `Frigate`. */
    hull_class: string
    /** Optional line under every ship's "Example fits" heading. */
    fits_lead?: string
    meta: { title: string; edition: string; yc: string }
    introduction: string[]
    considerations: string[]
    consideration_bullets: string[]
    disclaimers: string[]
    metagame_summary: { archetype: string; text: string }[]
    matchup_legend: GuideMatchupLegendItem[]
    matchup_charts: MatchupChart[]
    ships: ShipGuide[]
    glossary: GlossaryEntry[]
    sections: GuideSection[]
    resources: GuideResourceLink[]
    /** The lead-in paragraph above the resource list. */
    resources_intro: ResourcesIntroPart[]
    /** First-edition testimonials and thanks, shown under the lead-in. */
    credits?: { quotes: { text: string; attribution: string }[]; thanks: string }
    get_fittings: (ship_id: string) => GuideFitting[]
    resolve_opponent: OpponentShipResolver
}
