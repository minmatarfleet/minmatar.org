import { describe, expect, it } from 'vitest'

import {
    get_adjacent_issues,
    get_issue,
    get_issue_slugs,
    get_latest_issue,
    ISSUES,
    issue_label,
} from '@/data/amamake-market'
import { campaigns, getAllCampaigns, getMarketReports } from '@/data/campaigns'

describe('amamake market issue registry', () => {
    it('lists yc128-08 as the latest issue', () => {
        expect(get_latest_issue().slug).toBe('yc128-08')
        expect(get_issue('yc128-08')?.permalink_path).toBe('/amamake-market/yc128-08/')
        expect(get_issue_slugs()).toContain('yc128-08')
        expect(ISSUES).toHaveLength(1)
        expect(issue_label(get_latest_issue())).toBe('August YC128')
    })

    it('returns undefined for an unknown slug', () => {
        expect(get_issue('yc128-99')).toBeUndefined()
        expect(get_adjacent_issues('yc128-99')).toEqual({})
    })

    it('wires the generated sales totals into the issue', () => {
        const issue = get_latest_issue()
        expect(issue.sales.isk).toBeGreaterThan(0)
        expect(issue.sales.fills).toBeGreaterThan(0)
        expect(issue.weeks.length).toBeGreaterThan(3)
        expect(issue.catchment.rows[0]?.system).toBe('Amamake')
        expect(issue.hulls.rows.length).toBeGreaterThan(0)
    })
})

describe('amamake market content-hub registration', () => {
    it('lists the August issue as a market report on its permalink', () => {
        const entry = campaigns.find((campaign) => campaign.slug === 'amamake-market-yc128-08')

        expect(entry).toBeDefined()
        expect(entry?.kind).toBe('market')
        expect(entry?.path).toBe('/amamake-market/yc128-08/')
        expect(entry?.isk_label_key).toBe('sold')
        expect(entry?.iskDestroyed).toBe(get_latest_issue().sales.isk)
        expect(getMarketReports()[0]?.slug).toBe('amamake-market-yc128-08')
    })

    it('keeps market reports out of the campaigns strip', () => {
        expect(getAllCampaigns().some((campaign) => campaign.kind === 'market')).toBe(false)
    })
})
