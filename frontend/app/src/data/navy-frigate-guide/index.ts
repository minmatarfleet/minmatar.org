export { guideMeta, introduction, considerations, considerationBullets, disclaimers, metagameSummary, glossary, guideSections, additionalResources } from './content'
export type { GuideResource } from './content'
export { buildNavyFrigateGuideJsonLd } from './seo'
export { matchupLegend, brawlingChart, kitingChart, matchupCharts } from './matchup-charts'
export { hookbillGuide, cometGuide, slicerGuide, firetailGuide, vigilFleetGuide, tristanGuide, breacherGuide, shipGuides } from './ships'
export { guideFittings, getGuideFittingsForShip, getGuideFittingById } from './fittings'
export type {
    MatchupRating,
    GuideFitting,
    MatchupVerdict,
    ShipProseSection,
    MatchupEntry,
    MatchupGroup,
    ShipBonus,
    ShipGuide,
    GlossaryEntry,
    GuideSection,
    GuideHistoryEntry,
    MatchupChart,
} from './types'
