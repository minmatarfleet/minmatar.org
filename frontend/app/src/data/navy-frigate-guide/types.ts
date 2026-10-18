export type {
    MatchupRating,
    GuideFitting,
    ShipProseSection,
    MatchupVerdict,
    MatchupEntry,
    MatchupGroup,
    ShipBonus,
    ShipGuide,
    GlossaryEntry,
    GuideSection,
    MatchupChart,
} from '@/data/ship-guide/types'

export type GuideHistoryEntry = {
    id: string
    dateLabel: string
    yc: string
    title: string
    description: string
    link?: {
        href: string
        label: string
    }
}
