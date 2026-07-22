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

export type ParsedFitSection = {
    label: string
    modules: string[]
}
