import type { ShipGuideConfig } from '@/data/ship-guide/types'
import {
    guideMeta,
    credits,
    additionalResources,
    introduction,
    considerations,
    considerationBullets,
    disclaimers,
    metagameSummary,
    glossary,
    guideSections,
    matchupLegend,
    matchupCharts,
    shipGuides,
    getGuideFittingsForShip,
} from './index'
import { resolveMatchupOpponentShip } from './opponent-ships'

export const guide: ShipGuideConfig = {
    id_prefix: 'fwc',
    hull_class: 'Cruiser',
    fits_lead: 'Example fittings for each role above. Copy into Pyfa / EFT, then tune for your skills and contracts.',
    meta: guideMeta,
    introduction,
    considerations,
    consideration_bullets: considerationBullets,
    disclaimers,
    metagame_summary: metagameSummary,
    matchup_legend: matchupLegend,
    matchup_charts: matchupCharts,
    ships: shipGuides,
    glossary,
    sections: guideSections,
    resources: additionalResources,
    resources_intro: [
        `Written by ${credits.author}. The links below cover sibling hull guides, plex fundamentals, and deeper yearly data when you want another angle.`,
    ],
    get_fittings: getGuideFittingsForShip,
    resolve_opponent: resolveMatchupOpponentShip,
}
