export {
    guideMeta,
    credits,
    overview,
    overviewReasons,
    overviewFollowUp,
    metaBlocks,
    shipsLead,
    carrierHulls,
    carrierTiers,
    fightersTable,
    guideSections,
} from './content'
export {
    CAPITALS_TRIBE_ID,
    CARRIERS_GROUP_ID,
    CAPITALS_TRIBE_NAME,
    CARRIERS_GROUP_NAME,
    capitals_tribe_path,
    capitals_group_path,
    build_capitals_tribe_copy,
    load_capital_guide_runtime,
} from '@/data/capital-guide'

import { buildCapitalGuideJsonLd } from '@/data/capital-guide'

type JsonLdOptions = Omit<Parameters<typeof buildCapitalGuideJsonLd>[0], 'keywords'>

export function buildCarrierGuideJsonLd(options: JsonLdOptions) {
    return buildCapitalGuideJsonLd({
        ...options,
        keywords: [
            'EVE Online',
            'carrier',
            'Archon',
            'Thanatos',
            'Nidhoggur',
            'Chimera',
            'fighters',
            'suitcasing',
            'conduits',
            'capital ships',
            'Minmatar Fleet',
            'tier list',
        ],
    })
}
