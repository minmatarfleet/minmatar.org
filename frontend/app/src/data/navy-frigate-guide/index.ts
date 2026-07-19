export { guideMeta, introduction, considerations, considerationBullets, disclaimers, metagameSummary, glossary, guideSections, additionalResources } from './content'
export type { GuideResource } from './content'
export { buildNavyFrigateGuideJsonLd } from './seo'
export { matchupLegend, brawlingChart, kitingChart, matchupCharts } from './matchup-charts'
export { hookbillGuide, cometGuide, slicerGuide, firetailGuide, vigilFleetGuide, rifterGuide, tristanGuide, breacherGuide, shipGuides } from './ships'
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
    ParsedFitSection,
} from './types'

import type { GuideFitting, ParsedFitSection } from './types'

const EFT_SECTION_LABELS = ['Low slots', 'Mid slots', 'High slots', 'Rigs'] as const

/** Parse standard EFT layout without SDE slot validation (safe for guide SSR). */
export function parseEftSectionsLenient(eftFormat: string): ParsedFitSection[] {
    const sections: ParsedFitSection[] = []
    let sectionIndex = 0
    let current: string[] = []
    let started = false

    for (const rawLine of eftFormat.split(/\r?\n/)) {
        const line = rawLine.trim()

        if (!started) {
            if (line.startsWith('[') && line.endsWith(']')) started = true
            continue
        }

        if (line === '') {
            if (current.length === 0) continue

            if (sectionIndex < EFT_SECTION_LABELS.length) {
                sections.push({ label: EFT_SECTION_LABELS[sectionIndex], modules: current })
                sectionIndex++
            } else {
                appendCargoSection(sections, current)
            }
            current = []
            continue
        }

        current.push(line)
    }

    if (current.length > 0) {
        if (sectionIndex < EFT_SECTION_LABELS.length) {
            sections.push({ label: EFT_SECTION_LABELS[sectionIndex], modules: current })
        } else {
            appendCargoSection(sections, current)
        }
    }

    return sections
}

function appendCargoSection(sections: ParsedFitSection[], modules: string[]) {
    const existing = sections.find((section) => section.label === 'Cargo')
    if (existing) {
        existing.modules.push(...modules)
    } else {
        sections.push({ label: 'Cargo', modules })
    }
}

export function parseGuideFittingSections(fit: GuideFitting): ParsedFitSection[] {
    return parseEftSectionsLenient(fit.eftFormat)
}
