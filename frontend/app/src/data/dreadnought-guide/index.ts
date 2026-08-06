export {
    guideMeta,
    credits,
    overview,
    metaBlocks,
    shipsLead,
    guidanceLead,
    guidanceReasons,
    revelationSkillPlan,
    crosstrainingLead,
    crosstrainingRows,
    guideSections,
    dreadHulls,
    antiCapitalTier,
    hawTier,
    tierLists,
} from './content'
export {
    CAPITALS_TRIBE_ID,
    DREADS_GROUP_ID,
    CAPITALS_TRIBE_NAME,
    DREADS_GROUP_NAME,
    capitals_tribe_path,
    capitals_group_path,
    build_capitals_tribe_copy,
    load_capital_guide_runtime,
} from '@/data/capital-guide'

import { buildCapitalGuideJsonLd } from '@/data/capital-guide'

type JsonLdOptions = Omit<Parameters<typeof buildCapitalGuideJsonLd>[0], 'keywords'>

export function buildDreadnoughtGuideJsonLd(options: JsonLdOptions) {
    return buildCapitalGuideJsonLd({
        ...options,
        keywords: [
            'EVE Online',
            'dreadnought',
            'Revelation',
            'Zirnitra',
            'Naglfar',
            'Phoenix',
            'Moros',
            'anti-capital',
            'HAW',
            'high-angle',
            'crosstraining',
            'capital ships',
            'Minmatar Fleet',
            'tier list',
        ],
    })
}
