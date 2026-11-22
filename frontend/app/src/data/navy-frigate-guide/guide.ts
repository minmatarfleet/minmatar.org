import type { ShipGuideConfig } from '@/data/ship-guide/types'
import {
    guideMeta,
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
    id_prefix: 'nfg',
    hull_class: 'Frigate',
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
        'This guide stands on its own. The links below are where we looked for community practice, plex fundamentals, and deeper yearly data—use them when you want another angle.',
    ],
    get_fittings: getGuideFittingsForShip,
    resolve_opponent: resolveMatchupOpponentShip,
}
