import { COVER_IMAGE as ETHERIUM_COVER, CAMPAIGN_ISK_DESTROYED as ETHERIUM_ISK } from '@/data/campaigns/etherium-reach'
import { COVER_IMAGE as PROVIDENCE_COVER, CAMPAIGN_ISK_DESTROYED as PROVIDENCE_ISK } from '@/data/campaigns/providence'
import { COVER_IMAGE as SCALDING_COVER, PERIOD_SCALDING_ISK_KILLS as SCALDING_ISK } from '@/data/campaigns/scalding-pass'
import { COVER_IMAGE as HEK_COVER, ISK_DESTROYED as HEK_ISK } from '@/data/campaigns/hek'
import { COVER_IMAGE as AUGA_COVER, CAMPAIGN_ISK_DESTROYED as AUGA_ISK, ALLIANCE_PATH as AUGA_PATH, SLUG as AUGA_SLUG } from '@/data/campaigns/auga'
import { formatIsk } from '@/data/campaigns/hek'
import { COVER_IMAGE as WARZONE_COVER, PERMALINK_PATH as WARZONE_PATH, YC128_07 } from '@/data/warzone/yc128-07'
import { PERMALINK_PATH as WARZONE_08_PATH, YC128_08 } from '@/data/warzone/yc128-08'
import {
    COVER_IMAGE as AMAMAKE_COVER,
    PERMALINK_PATH as AMAMAKE_08_PATH,
    YC128_08 as AMAMAKE_YC128_08,
} from '@/data/amamake-market/yc128-08'

export type CampaignKind = 'campaign' | 'siege' | 'warzone' | 'market'

export type CampaignMeta = {
    slug: string
    path: string
    nameKey: string
    periodKey: string
    excerptKey: string
    coverImage: string
    iskDestroyed: number
    sortOrder: number
    kind: CampaignKind
    /** i18n key for the card's ISK figure label. Defaults to `destroyed`. */
    isk_label_key?: string
    /** Campaign/siege end date for content-stream sorting. */
    published_at: Date
}

export const campaigns: CampaignMeta[] = [
    {
        slug: 'etherium-reach',
        path: '/alliance/campaigns/etherium-reach/',
        nameKey: 'campaigns.etherium_reach.name',
        periodKey: 'campaigns.etherium_reach.campaign_period',
        excerptKey: 'campaigns.etherium_reach.leading_text',
        coverImage: ETHERIUM_COVER,
        iskDestroyed: ETHERIUM_ISK,
        sortOrder: 1,
        kind: 'campaign',
        published_at: new Date('2026-06-18T00:00:00Z'),
    },
    {
        slug: 'providence',
        path: '/alliance/campaigns/providence/',
        nameKey: 'campaigns.providence.name',
        periodKey: 'campaigns.providence.campaign_period',
        excerptKey: 'campaigns.providence.leading_text',
        coverImage: PROVIDENCE_COVER,
        iskDestroyed: PROVIDENCE_ISK,
        sortOrder: 2,
        kind: 'campaign',
        published_at: new Date('2025-03-31T00:00:00Z'),
    },
    {
        slug: 'scalding-pass',
        path: '/alliance/campaigns/scalding-pass/',
        nameKey: 'campaigns.scalding_pass.name',
        periodKey: 'campaigns.scalding_pass.campaign_period',
        excerptKey: 'campaigns.scalding_pass.leading_text',
        coverImage: SCALDING_COVER,
        iskDestroyed: SCALDING_ISK,
        sortOrder: 3,
        kind: 'campaign',
        published_at: new Date('2024-05-31T00:00:00Z'),
    },
    {
        slug: 'hek',
        path: '/alliance/campaigns/hek/',
        nameKey: 'campaigns.hek.name',
        periodKey: 'campaigns.hek.campaign_period',
        excerptKey: 'campaigns.hek.leading_text',
        coverImage: HEK_COVER,
        iskDestroyed: HEK_ISK,
        sortOrder: 4,
        kind: 'campaign',
        published_at: new Date('2023-11-30T00:00:00Z'),
    },
    {
        slug: AUGA_SLUG,
        path: AUGA_PATH,
        nameKey: 'campaigns.auga.name',
        periodKey: 'campaigns.auga.campaign_period',
        excerptKey: 'campaigns.auga.leading_text',
        coverImage: AUGA_COVER,
        iskDestroyed: AUGA_ISK,
        sortOrder: 1,
        kind: 'siege',
        published_at: new Date('2026-07-18T00:00:00Z'),
    },
    {
        slug: 'yc128-07',
        path: WARZONE_PATH,
        nameKey: 'warzone.yc128_07.name',
        periodKey: 'warzone.yc128_07.period',
        excerptKey: 'warzone.yc128_07.leading_text',
        coverImage: WARZONE_COVER,
        iskDestroyed: YC128_07.sampled_isk,
        sortOrder: 0,
        kind: 'warzone',
        published_at: new Date('2026-07-31T00:00:00Z'),
    },
    {
        slug: 'yc128-08',
        path: WARZONE_08_PATH,
        nameKey: 'warzone.yc128_08.name',
        periodKey: 'warzone.yc128_08.period',
        excerptKey: 'warzone.yc128_08.leading_text',
        coverImage: WARZONE_COVER,
        iskDestroyed: YC128_08.sampled_isk,
        sortOrder: 0,
        kind: 'warzone',
        published_at: new Date('2026-08-31T00:00:00Z'),
    },
    {
        slug: 'amamake-market-yc128-08',
        path: AMAMAKE_08_PATH,
        nameKey: 'amamake_market.yc128_08.name',
        periodKey: 'amamake_market.yc128_08.period',
        excerptKey: 'amamake_market.yc128_08.leading_text',
        coverImage: AMAMAKE_COVER,
        iskDestroyed: AMAMAKE_YC128_08.sales.isk,
        sortOrder: 0,
        kind: 'market',
        isk_label_key: 'sold',
        published_at: AMAMAKE_YC128_08.published_at,
    },
]

export function getCampaigns(): CampaignMeta[] {
    return campaigns
        .filter((c) => c.kind === 'campaign')
        .sort((a, b) => a.sortOrder - b.sortOrder)
}

export function getSieges(): CampaignMeta[] {
    return campaigns
        .filter((c) => c.kind === 'siege')
        .sort((a, b) => a.sortOrder - b.sortOrder)
}

/** Campaigns and sieges; the monthly report series have their own strips. */
export function getAllCampaigns(): CampaignMeta[] {
    return campaigns
        .filter((c) => c.kind !== 'warzone' && c.kind !== 'market')
        .sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

export function getWarzoneReports(): CampaignMeta[] {
    return campaigns
        .filter((c) => c.kind === 'warzone')
        .sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

export function getMarketReports(): CampaignMeta[] {
    return campaigns
        .filter((c) => c.kind === 'market')
        .sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

export { formatIsk }
