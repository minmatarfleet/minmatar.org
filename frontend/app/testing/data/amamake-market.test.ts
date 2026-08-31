import { describe, expect, it } from 'vitest'

import { campaigns, getAllCampaigns } from '@/data/campaigns'
import { CANONICAL_PATH, SLUG } from '@/data/campaigns/amamake-market'

describe('amamake market campaign registry', () => {
    it('lists the August issue on the public canonical path', () => {
        const entry = campaigns.find((campaign) => campaign.slug === SLUG)

        expect(entry).toBeDefined()
        expect(entry?.kind).toBe('market')
        expect(entry?.path).toBe(CANONICAL_PATH)
        expect(entry?.isk_label_key).toBe('sold')
        expect(entry?.iskDestroyed).toBeGreaterThan(1_000_000_000_000)
        expect(getAllCampaigns()[0]?.slug).toBe(SLUG)
    })
})
