import { describe, expect, it } from 'vitest'

import type { CampaignFeatures, CampaignStructure } from '@dtypes/api.minmatar.org'
import { campaign_tabs, features_on, sort_campaign_structures } from '@helpers/campaign_features'

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
            .toEqual(['structures', 'fleets', 'activity', 'pilots', 'projects', 'you', 'roles', 'settings'])
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
            .toEqual(['structures', 'timers', 'fleets', 'destruction', 'you', 'roles', 'settings'])
        expect(features_on(features)).toBe(4)
    })

    it('keeps the activity feed next to destruction on a faction warfare campaign', () => {
        const features = { ...ALL_TODAY, destruction: true }
        expect(campaign_tabs({ kind: 'faction_warfare', features, has_systems: true, can_manage: false }))
            .toContain('activity')
    })
})

describe('campaign structure order', () => {
    const row = (name: string, status: CampaignStructure['status'], timer_at: string | null = null, destroyed_at: string | null = null) =>
        ({ name, status, timer_at, destroyed_at } as CampaignStructure)

    it('puts reinforced by next timer first, anchored next, destroyed last', () => {
        const sorted = sort_campaign_structures([
            row('Dead', 'destroyed', null, '2026-01-02T00:00:00Z'),
            row('Calm', 'anchored'),
            row('Later', 'reinforced', '2026-01-05T00:00:00Z'),
            row('Sooner', 'reinforced', '2026-01-04T00:00:00Z'),
        ])
        expect(sorted.map((structure) => structure.name)).toEqual(['Sooner', 'Later', 'Calm', 'Dead'])
    })
})

describe('campaign roles tab', () => {
    const features = { structures: true, timers: true, fleets: true, theater: false, destruction: true, pilots: false, projects: false }

    it('gives a role holder in the coordinator view their shared tabs and Roles', () => {
        expect(campaign_tabs({ kind: 'strategic', features: features as never, has_systems: false, can_manage: false, coordinator_scopes: ['fleets'], has_roles: true }))
            .toEqual(['fleets', 'roles', 'discord'])
    })

    it('hides Roles from plain members', () => {
        expect(campaign_tabs({ kind: 'strategic', features: features as never, has_systems: false, can_manage: false })).not.toContain('roles')
    })
})
