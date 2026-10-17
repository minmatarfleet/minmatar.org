import { describe, expect, it } from 'vitest'

import { readFileSync } from 'fs'

import type { CampaignSystemSummary, CampaignWeek, CampaignWeekObjectiveRow, CampaignWeekTarget } from '@dtypes/api.minmatar.org'
import { campaign_objective_rows, contest_bar_percent, week_contest_marker, week_contest_move, week_move_color } from '@helpers/fetching/campaigns'

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
            row({ target_id: 1, system_id: 1, name: 'Kamela', objective: 'capture_complexes', progress_percent: 42.5, change_24h: 4 }),
            row({ target_id: 2, system_id: 2, name: 'Huola', objective: 'defend_complexes', progress_percent: 88, change_24h: -5 }),
        ]), [], objective_t)

        const kamela = rows.find(row => row.system_name === 'Kamela')
        const huola = rows.find(row => row.system_name === 'Huola')

        expect(kamela?.now_text).toBe('42.5%')
        expect(kamela?.meter_percent).toBeCloseTo(42.5)
        expect(kamela?.marker_percent).toBeNull()
        expect(kamela?.target_text).toBe('')
        expect(kamela?.change_text).toBe('+4%')
        expect(kamela?.change_direction).toBe('up')
        expect(huola?.now_text).toBe('88%')
        expect(huola?.meter_percent).toBeCloseTo(88)
        expect(huola?.delta_from_percent).toBeCloseTo(93)
        expect(huola?.marker_percent).toBeNull()
        expect(huola?.change_text).toBe('-5%')
        expect(huola?.change_direction).toBe('down')
    })

    it('describes complex rows in victory points, never contested percent', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 4, name: 'Auga', objective: 'defend_complexes', progress_percent: 98.4, victory_points: 1230, victory_points_threshold: 75000 }),
            row({ target_id: 5, name: 'Dal', objective: 'capture_complexes', progress_percent: 13.4, victory_points: 0, victory_points_threshold: 0 }),
        ]), [], objective_t)

        expect(rows.find(row => row.system_name === 'Auga')?.detail_text).toBe('1,230 of 75,000 victory points')
        expect(rows.find(row => row.system_name === 'Dal')?.detail_text).toBe('')
    })

    it('prints the move in whole points, and a move under half a point as steady', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 6, name: 'Siseide', objective: 'defend_complexes', progress_percent: 100, change_24h: -0.4 }),
        ]), [], objective_t)

        expect(rows[0]?.change_text).toBe('0%')
        expect(rows[0]?.change_direction).toBe('flat')
    })

    it('inverts a destroy row so the bar fills as their advantage falls', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 7, name: 'Kamela', objective: 'destroy_advantage', progress_percent: 55, change_week: 15, advantage_level: 45 }),
        ]), [], objective_t)

        expect(rows[0]?.meter_percent).toBe(55)
        expect(rows[0]?.delta_from_percent).toBe(40)
        expect(rows[0]?.change_label).toBe('week')
        expect(rows[0]?.change_text).toBe('+15%')
        expect(rows[0]?.change_direction).toBe('up')
        expect(rows[0]?.detail_text).toBe('theirs 45%')
    })

    it('reads a stable hold as 100% progress', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 3, name: 'Kourmonen', objective: 'defend_complexes', progress_percent: 100, change_24h: 0 }),
        ]), [], objective_t)

        expect(rows[0]?.now_text).toBe('100%')
        expect(rows[0]?.meter_percent).toBe(100)
    })

    it('shows no figure before a system has a reading', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 3, name: 'Vard', objective: 'capture_complexes', progress_percent: null }),
        ]), [], objective_t)

        expect(rows[0]?.now_text).toBe('')
        expect(rows[0]?.meter_percent).toBe(0)
        expect(rows[0]?.change_text).toBe('')
    })

    it('measures complex rows from where the week opened, keeping the day for the hover', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 8, name: 'Kamela', objective: 'capture_complexes', progress_percent: 42.5, change_week: 12.5, change_24h: -2 }),
            row({ target_id: 9, name: 'Huola', objective: 'defend_complexes', progress_percent: 88, change_week: -8, change_24h: -1 }),
        ]), [], objective_t)

        const kamela = rows.find(row => row.system_name === 'Kamela')
        const huola = rows.find(row => row.system_name === 'Huola')

        expect(kamela?.change_label).toBe('week')
        expect(kamela?.change_text).toBe('+13%')
        expect(kamela?.change_direction).toBe('up')
        expect(kamela?.delta_from_percent).toBeCloseTo(30)
        expect(kamela?.change_24h_text).toBe('-2%')
        expect(huola?.change_label).toBe('week')
        expect(huola?.change_text).toBe('-8%')
        expect(huola?.change_direction).toBe('down')
        expect(huola?.change_24h_text).toBe('-1%')
    })

    it('shows a flip instead of a move when the system changed hands this week', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: 10, name: 'Kamela', objective: 'capture_complexes', progress_percent: 5, change_24h: -85, flipped: 'captured' }),
        ]), [], objective_t)

        expect(rows[0]?.flipped).toBe('captured')
        expect(rows[0]?.change_label).toBe('week')
        expect(rows[0]?.change_text).toBe('')
        expect(rows[0]?.delta_from_percent).toBeNull()
        expect(rows[0]?.change_24h_text).toBe('-85%')
    })

    it('falls back to the day when the week has no reading for the system', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: null, name: 'Kamela', objective: 'capture_complexes', progress_percent: 20, change_24h: 3 }),
        ]), [], objective_t)

        expect(rows[0]?.change_label).toBe('24h')
        expect(rows[0]?.change_text).toBe('+3%')
        expect(rows[0]?.change_24h_text).toBe('')
        expect(rows[0]?.flipped).toBeNull()
    })

    it('keeps the backend order and joins the viewer\'s share and the system by id', () => {
        const kamela = system({ id: 11, name: 'Kamela', goal: 'take', status_chip: 'losing' })
        const week = week_with([
            row({ target_id: 21, system_id: 12, name: 'Huola', objective: 'capture_complexes', pace: 'behind' }),
            row({ target_id: 20, system_id: 11, name: 'Kamela', objective: 'capture_complexes', pace: 'ahead' }),
        ])
        week.targets = [target({ id: 20, system: 'Kamela', goal: 'take', metric: 'victory_points', my_complexes: 2 })]

        const rows = campaign_objective_rows(week, [kamela], objective_t)

        expect(rows.map(row => row.key)).toEqual(['target-21', 'target-20'])
        expect(rows[0]?.status).toBe('losing')
        expect(rows[0]?.system).toBeNull()
        expect(rows[1]?.system?.id).toBe(11)
        expect(rows[1]?.yours_text).toBe('campaigns.objective.yours_complexes')
    })

    it('reads a row without a target as on pace or behind from its system', () => {
        const rows = campaign_objective_rows(week_with([
            row({ target_id: null, system_id: 11, name: 'Kamela', objective: 'capture_complexes', pace: null }),
        ]), [system({ id: 11, name: 'Kamela', goal: 'take', status_chip: 'holding' })], objective_t)

        expect(rows[0]?.key).toBe('system-11')
        expect(rows[0]?.pace).toBe('behind')
        expect(rows[0]?.status).toBe('losing')
    })

    it('draws the contract week the backend generates', () => {
        const { week, systems } = JSON.parse(readFileSync('testing/contracts/campaign_week.json', 'utf8'))
        const rows = campaign_objective_rows(week, systems, objective_t)

        expect(rows.map(row => [row.system_name, row.label, row.now_text, row.change_text, row.change_label, row.status])).toEqual([
            ['Kourmonen', 'campaigns.objective.defend_complexes', '87%', '+7%', 'week', 'winning'],
            ['Kamela', 'campaigns.objective.run_complexes', '62%', '+32%', 'week', 'losing'],
            ['Kamela', 'campaigns.objective.gain_advantage', '0%', '0%', 'week', 'winning'],
            ['Vard', 'campaigns.objective.run_complexes', '', '', '24h', 'winning'],
            ['Huola', 'campaigns.objective.run_complexes', '10%', '', 'week', 'winning'],
            ['Sosala', 'campaigns.objective.destroy_advantage', '65%', '+25%', 'week', 'winning'],
            ['Arzad', 'campaigns.objective.maintain_advantage', '41%', '+11%', 'week', 'winning'],
            ['Bosboger', 'campaigns.objective.report_structures', 'campaigns.objective.value_structure', '', 'week', 'winning'],
        ])
        expect(rows.find(row => row.system_name === 'Huola')?.flipped).toBe('captured')
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
        case 'campaigns.objective.victory_points_of': return '{value} of {threshold} victory points'
        case 'campaigns.objective.level_theirs': return 'theirs {level}%'
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

const row = (overrides:Partial<CampaignWeekObjectiveRow> & Pick<CampaignWeekObjectiveRow, 'name' | 'objective'>):CampaignWeekObjectiveRow => ({
    target_id: 1,
    system_id: overrides.name.length,
    solar_system_id: 1,
    priority: 'medium',
    holder: null,
    pace: 'on_pace',
    proposed: false,
    progress_percent: 0,
    change_week: null,
    change_24h: null,
    flipped: null,
    contested_percent: null,
    victory_points: null,
    victory_points_threshold: null,
    advantage_level: null,
    structures_reported: null,
    structures_target: null,
    ...overrides,
})

const week_with = (objective_rows:CampaignWeekObjectiveRow[]):CampaignWeek => ({
    week_start: '2026-10-13',
    week_end: '2026-10-20',
    week_index: 1,
    week_count: 4,
    day_index: 1,
    targets: [],
    objective_rows,
    commander_order_text: '',
    summary: {},
})
