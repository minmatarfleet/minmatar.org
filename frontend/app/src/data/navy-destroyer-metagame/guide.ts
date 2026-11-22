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
    id_prefix: 'ndm',
    hull_class: 'Destroyer',
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
        'This web edition builds on Furl0w’s ',
        { href: guideMeta.firstEditionUrl, label: credits.firstEditionLabel },
        ' . The links below go deeper—original source, yearly meta references, and related guides on this site.',
    ],
    credits: { quotes: credits.quotes, thanks: credits.thanks },
    get_fittings: getGuideFittingsForShip,
    resolve_opponent: resolveMatchupOpponentShip,
}
