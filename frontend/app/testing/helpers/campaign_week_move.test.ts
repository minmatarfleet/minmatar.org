import { describe, expect, it } from 'vitest'

import type { CampaignSystemSummary, CampaignWeek, CampaignWeekTarget } from '@dtypes/api.minmatar.org'
import { campaign_objective_rows, contest_bar_percent, progress_bar_color, week_contest_marker, week_contest_move, week_move_color } from '@helpers/fetching/campaigns'

describe('week_contest_move', () => {
    it('treats a falling or low hold as good and a rising hold as bad', () => {
        expect(week_contest_move('hold', 20, 9.5)).toBe('ahead')
        expect(week_contest_move('hold', 8, 8.2)).toBe('holding')
        expect(week_contest_move('hold', 40, 40)).toBe('behind')
        expect(week_contest_move('hold', 12, 28)).toBe('slipping')
        expect(week_move_color('ahead')).toBe('green')
        expect(week_move_color('holding')).toBe('fleet-yellow')
        expect(week_move_color('slipping')).toBe('fleet-red')
        expect(week_move_color('behind')).toBe('fleet-red')
    })

    it('treats contested rising toward the threshold as good on a push', () => {
        expect(week_contest_move('take', 20, 35.26)).toBe('ahead')
        expect(week_contest_move('pressure', 35, 20)).toBe('slipping')
        expect(week_contest_move('take', 30, 30)).toBe('behind')
        expect(week_contest_move('pressure', 82, 82.2)).toBe('holding')
        expect(week_contest_marker('hold')).toBe(10)
        expect(week_contest_marker('take')).toBe(80)
    })

    it('fills a hold bar when the system is stable and empties it as the other side scores', () => {
        expect(contest_bar_percent('hold', 0)).toBe(100)
        expect(contest_bar_percent('defend', 3.2)).toBeCloseTo(96.8)
        expect(contest_bar_percent('take', 3.2)).toBeCloseTo(3.2)
        expect(contest_bar_percent('pressure', 0)).toBe(0)
        expect(contest_bar_percent('hold', null)).toBe(100)
    })

    it('shows progress percent with no goal tick, and inverts a hold', () => {
        const rows = campaign_objective_rows(week_with([
            target({ id: 1, system: 'Kamela', goal: 'take', metric: 'victory_points', progress: 1800, target: 3000, pace_expected: 900 }),
            target({ id: 2, system: 'Huola', goal: 'hold', metric: 'days_under_line', progress: 4, target: 7, pace_expected: 3 }),
        ]), [
            system({ name: 'Kamela', goal: 'take', contested_percent: 42.5, contested_change_24h: 4 }),
            system({ name: 'Huola', goal: 'hold', contested_percent: 12, contested_change_24h: 5 }),
        ], objective_t)

        const kamela = rows.find(row => row.system_name === 'Kamela')
        const huola = rows.find(row => row.system_name === 'Huola')

        expect(kamela?.now_text).toBe('42.5%')
        expect(kamela?.detail_text).toBe('')
        expect(kamela?.meter_percent).toBeCloseTo(42.5)
        expect(kamela?.marker_percent).toBeNull()
        expect(kamela?.target_text).toBe('')
        expect(huola?.now_text).toBe('88%')
        expect(huola?.detail_text).toBe('12.0% contested')
        expect(huola?.meter_percent).toBeCloseTo(88)
        expect(huola?.delta_from_percent).toBeCloseTo(93)
        expect(huola?.marker_percent).toBeNull()
        expect(huola?.change_direction).toBe('down')
    })

    it('reads a stable hold as 100% progress', () => {
        const rows = campaign_objective_rows(week_with([
            target({ id: 3, system: 'Kourmonen', goal: 'hold', metric: 'days_under_line' }),
        ]), [
            system({ name: 'Kourmonen', goal: 'hold', contested_percent: 0, contested_change_24h: 0 }),
        ], objective_t)

        expect(rows[0]?.now_text).toBe('100%')
        expect(rows[0]?.detail_text).toBe('stable')
        expect(rows[0]?.meter_percent).toBe(100)
    })

    it('colors a bar from progress, so a stable hold is green and a slipping one is not', () => {
        expect(progress_bar_color('defense', 100)).toBe('green')
        expect(progress_bar_color('defense', 88)).toBe('fleet-yellow')
        expect(progress_bar_color('defense', 30)).toBe('fleet-red')
        expect(progress_bar_color('offense', 42.5)).toBe('fleet-yellow')
        expect(progress_bar_color('offense', 80)).toBe('green')
        expect(progress_bar_color('offense', 12)).toBe('fleet-red')
    })

    it('counts our advantage rising as good only while we are pushing', () => {
        expect(week_contest_move('take', 30, 30, 20, 35)).toBe('ahead')
        expect(week_contest_move('pressure', 30, 30, 40, 25)).toBe('slipping')
        expect(week_contest_move('take', 20, 35, 40, 25)).toBe('ahead')
        expect(week_contest_move('hold', 8, 8, 20, 40)).toBe('holding')
    })
})

const objective_t = (key:string):string => {
    switch (key) {
        case 'campaigns.objective.stable': return 'stable'
        case 'campaigns.objective.contested_now': return '{contested}% contested'
        default: return key
    }
}

const target = (overrides:Partial<CampaignWeekTarget> & Pick<CampaignWeekTarget, 'id' | 'system' | 'goal' | 'metric'>):CampaignWeekTarget => ({
    system_id: overrides.id,
    target: 1,
    progress: 0,
    pace_expected: 0,
    baseline: 0,
    pace: 'on_pace',
    proposed: false,
    last_week_actual: 0,
    days_under_line: 0,
    projected_arc_date: null,
    my_complexes: 0,
    my_advantage_sites: 0,
    my_readings: 0,
    ...overrides,
})

const system = (overrides:Partial<CampaignSystemSummary> & Pick<CampaignSystemSummary, 'name' | 'goal'>):CampaignSystemSummary => ({
    id: overrides.name.length,
    solar_system_id: 1,
    role: 'primary',
    priority: 'medium',
    is_fw_objective: true,
    contested_percent: 0,
    contested_change_24h: 0,
    victory_points: 0,
    victory_points_threshold: 0,
    operational_state: 'frontline',
    contested_updated_at: null,
    advantage_updated_at: null,
    occupier_faction_id: null,
    owner_faction_id: null,
    advantage_basis: 'unknown',
    advantage_source: 'frontlines',
    advantage_our_pct: null,
    advantage_enemy_pct: null,
    advantage_net_pct: null,
    advantage_age_minutes: null,
    advantage_is_stale: false,
    kills_24h: 0,
    losses_24h: 0,
    kills_change_24h: 0,
    trend: [],
    status_chip: 'holding',
    ...overrides,
})

const week_with = (targets:CampaignWeekTarget[]):CampaignWeek => ({
    week_start: '2026-10-13',
    week_end: '2026-10-20',
    week_index: 1,
    week_count: 4,
    day_index: 1,
    targets,
    commander_order_text: '',
    summary: {},
})
