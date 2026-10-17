import { describe, expect, it } from 'vitest'
import {
    contributor_share,
    parse_project_action,
    project_isk_paid,
    project_kind_label,
    project_percent,
    project_state_color,
    project_target_label,
    sort_projects,
} from '@helpers/corporations/projects'
import { ui } from '@i18n/ui'

const t = (key: keyof typeof ui['en']) => ui.en[key]

describe('corporation projects', () => {
    it('labels every ESI configuration kind and falls back for new ones', () => {
        expect(project_kind_label('capture_fw_complex', t)).toBe('Capture FW complexes')
        expect(project_kind_label('manual', t)).toBe('Manual')
        expect(project_kind_label('hack_relic_site', t)).toBe('Hack relic site')
        expect(project_target_label('locations', t)).toBe('Where')
        expect(project_target_label('signatures', t)).toBe('Signatures')
    })

    it('caps progress and survives a project with no goal', () => {
        expect(project_percent({ progress_current: 5, progress_desired: 20 })).toBe(25)
        expect(project_percent({ progress_current: 30, progress_desired: 20 })).toBe(100)
        expect(project_percent({ progress_current: 0, progress_desired: 0 })).toBe(0)
    })

    it('reports ISK paid only when ESI gave both figures', () => {
        expect(project_isk_paid({ reward_initial: 100, reward_remaining: 40 })).toBe(60)
        expect(project_isk_paid({ reward_initial: null, reward_remaining: 40 })).toBeNull()
    })

    it('splits contributor shares over the recorded total', () => {
        const rows = [
            { character_id: 1, character_name: 'A', contributed: 3 },
            { character_id: 2, character_name: 'B', contributed: 1 },
        ]
        expect(contributor_share(rows[0], rows)).toBe(75)
        expect(contributor_share(rows[0], [{ ...rows[0], contributed: 0 }])).toBe(0)
    })

    it('greys out stopped projects', () => {
        expect(project_state_color('Active')).toBe('green')
        expect(project_state_color('Completed')).toBe('alliance-blue')
        expect(project_state_color('Expired')).toBe('border-color')
    })

    it('only accepts known form actions', () => {
        expect(parse_project_action('attach')).toBe('attach')
        expect(parse_project_action('detach')).toBe('detach')
        expect(parse_project_action('refresh')).toBe('refresh')
        expect(parse_project_action('delete')).toBeNull()
    })

    it('puts active projects first, newest change first', () => {
        const sorted = sort_projects([
            { state: 'Completed', last_modified: '2026-10-03T00:00:00Z' },
            { state: 'Active', last_modified: '2026-10-01T00:00:00Z' },
            { state: 'Active', last_modified: '2026-10-02T00:00:00Z' },
        ])
        expect(sorted.map((row) => `${row.state} ${row.last_modified.slice(8, 10)}`)).toEqual([
            'Active 02',
            'Active 01',
            'Completed 03',
        ])
    })
})
