import { COVER_IMAGE as ETHERIUM_COVER, CAMPAIGN_ISK_DESTROYED as ETHERIUM_ISK } from '@/data/campaigns/etherium-reach'
import { COVER_IMAGE as PROVIDENCE_COVER, CAMPAIGN_ISK_DESTROYED as PROVIDENCE_ISK } from '@/data/campaigns/providence'
import { COVER_IMAGE as SCALDING_COVER, PERIOD_SCALDING_ISK_KILLS as SCALDING_ISK } from '@/data/campaigns/scalding-pass'
import { COVER_IMAGE as HEK_COVER, ISK_DESTROYED as HEK_ISK } from '@/data/campaigns/hek'
import { formatIsk } from '@/data/campaigns/hek'

export type CampaignMeta = {
    slug: string
    path: string
    nameKey: string
    periodKey: string
    excerptKey: string
    coverImage: string
    iskDestroyed: number
    sortOrder: number
}

export const campaigns: CampaignMeta[] = [
    {
        slug: 'etherium-reach',
        path: '/campaigns/etherium-reach/',
        nameKey: 'campaigns.etherium_reach.name',
        periodKey: 'campaigns.etherium_reach.campaign_period',
        excerptKey: 'campaigns.etherium_reach.leading_text',
        coverImage: ETHERIUM_COVER,
        iskDestroyed: ETHERIUM_ISK,
        sortOrder: 1,
    },
    {
        slug: 'providence',
        path: '/campaigns/providence/',
        nameKey: 'campaigns.providence.name',
        periodKey: 'campaigns.providence.campaign_period',
        excerptKey: 'campaigns.providence.leading_text',
        coverImage: PROVIDENCE_COVER,
        iskDestroyed: PROVIDENCE_ISK,
        sortOrder: 2,
    },
    {
        slug: 'scalding-pass',
        path: '/campaigns/scalding-pass/',
        nameKey: 'campaigns.scalding_pass.name',
        periodKey: 'campaigns.scalding_pass.campaign_period',
        excerptKey: 'campaigns.scalding_pass.leading_text',
        coverImage: SCALDING_COVER,
        iskDestroyed: SCALDING_ISK,
        sortOrder: 3,
    },
    {
        slug: 'hek',
        path: '/campaigns/hek/',
        nameKey: 'campaigns.hek.name',
        periodKey: 'campaigns.hek.campaign_period',
        excerptKey: 'campaigns.hek.leading_text',
        coverImage: HEK_COVER,
        iskDestroyed: HEK_ISK,
        sortOrder: 4,
    },
]

export function getCampaigns(): CampaignMeta[] {
    return [...campaigns].sort((a, b) => a.sortOrder - b.sortOrder)
}

export { formatIsk }
