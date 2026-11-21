import { describe, expect, it } from 'vitest'

import type { CampaignFeatures } from '@dtypes/api.minmatar.org'
import { campaign_tabs, features_on } from '@helpers/campaign_features'

const ALL_TODAY: CampaignFeatures = {
    weekly_progress: true,
    structures: false,
    timers: false,
    theater: true,
    fleets: true,
    destruction: false,
    pilots: true,
    projects: true,
}

describe('campaign tabs', () => {
    it('keeps the tabs an existing faction warfare campaign shows today', () => {
        expect(campaign_tabs({ kind: 'faction_warfare', features: ALL_TODAY, has_systems: true, can_manage: false }))
            .toEqual(['systems', 'fleets', 'activity', 'pilots', 'projects', 'you'])
    })

    it('keeps the tabs an existing strategic campaign shows today', () => {
        const features = { ...ALL_TODAY, structures: true }
        expect(campaign_tabs({ kind: 'strategic', features, has_systems: false, can_manage: true }))
            .toEqual(['structures', 'fleets', 'activity', 'pilots', 'projects', 'you', 'settings'])
    })

    it('gives the strategic preset its structure campaign tabs', () => {
        const features: CampaignFeatures = {
            weekly_progress: false,
            structures: true,
            timers: true,
            theater: false,
            fleets: true,
            destruction: true,
            pilots: false,
            projects: false,
        }
        expect(campaign_tabs({ kind: 'strategic', features, has_systems: true, can_manage: true }))
            .toEqual(['structures', 'timers', 'fleets', 'destruction', 'you', 'settings'])
        expect(features_on(features)).toBe(4)
    })

    it('keeps the activity feed next to destruction on a faction warfare campaign', () => {
        const features = { ...ALL_TODAY, destruction: true }
        expect(campaign_tabs({ kind: 'faction_warfare', features, has_systems: true, can_manage: false }))
            .toContain('activity')
    })
})
