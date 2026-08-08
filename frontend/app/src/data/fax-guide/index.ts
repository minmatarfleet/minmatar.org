export {
    guideMeta,
    credits,
    overview,
    metaBlocks,
    guidanceLead,
    apostleSkillPlan,
    ninazuSkillPlan,
    guideSections,
} from './content'
export {
    CAPITALS_TRIBE_ID,
    FAXES_GROUP_ID,
    CAPITALS_TRIBE_NAME,
    FAXES_GROUP_NAME,
    capitals_tribe_path,
    capitals_group_path,
    build_capitals_tribe_copy,
    load_capital_guide_runtime,
} from '@/data/capital-guide'

import { buildCapitalGuideJsonLd } from '@/data/capital-guide'

type JsonLdOptions = Omit<Parameters<typeof buildCapitalGuideJsonLd>[0], 'keywords'>

export function buildFaxGuideJsonLd(options: JsonLdOptions) {
    return buildCapitalGuideJsonLd({
        ...options,
        keywords: [
            'EVE Online',
            'force auxiliary',
            'FAX',
            'triage',
            'Apostle',
            'Ninazu',
            'Lif',
            'Minokawa',
            'skill plan',
            'capital ships',
            'Minmatar Fleet',
        ],
    })
}
