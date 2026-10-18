export type {
    MatchupRating,
    GuideFitting,
    ShipProseSection,
    MatchupVerdict,
    MatchupEntry,
    MatchupGroup,
    ShipBonus,
    ShipGuide,
    MatchupChart,
} from '@/data/ship-guide/types'

export type GlossaryEntry = {
    term: string
    definition: string
}

export type GuideSection = {
    id: string
    title: string
    shortTitle?: string
}

export type ParsedFitSection = {
    label: string
    modules: string[]
}
