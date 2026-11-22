import { describe, expect, it } from 'vitest'
import { eve_time_iso, parse_selected_item_timer } from '@helpers/selected_item_timer'

describe('parse_selected_item_timer', () => {
    it('reads a citadel copied from Selected Item', () => {
        const parsed = parse_selected_item_timer('Amamake - Cylinder Must Remain Unharmed\n8.6 AU\nAnchoring until 2026.11.22 00:41:49')
        expect(parsed).toMatchObject({
            system_name: 'Amamake',
            name: 'Cylinder Must Remain Unharmed',
            state: 'anchoring',
            date: '2026-11-22',
            time: '00:41:49',
        })
    })

    it('keeps dashes inside the structure name', () => {
        const parsed = parse_selected_item_timer('Sosala - code - minmatar\r\n48 km\r\nReinforced until 2024.06.30 00:04:16')
        expect(parsed.system_name).toBe('Sosala')
        expect(parsed.name).toBe('code - minmatar')
        // Reinforced is armor or hull: the pilot picks.
        expect(parsed.state).toBe('')
    })

    it('reads a skyhook with its owner', () => {
        const parsed = parse_selected_item_timer('Orbital Skyhook (KBP7-G III) [Sukanan Inititive]\n0.5 AU\nReinforced until 2024.07.17 11:10:47')
        expect(parsed).toMatchObject({
            system_name: 'KBP7-G',
            name: 'Orbital Skyhook (KBP7-G III)',
            corporation_name: 'Sukanan Inititive',
            structure_type: 'orbital_skyhook',
            date: '2024-07-17',
        })
    })

    it('reads a jump gate as the system it stands in', () => {
        const parsed = parse_selected_item_timer('Kamela » Amamake - Knock Knock Bridge\n3.1 AU')
        expect(parsed.system_name).toBe('Kamela')
        expect(parsed.name).toBe('Knock Knock Bridge')
    })

    it('reads a structure with no timer line', () => {
        const parsed = parse_selected_item_timer('Kamela - Knock Knock\n3.1 AU')
        expect(parsed).toMatchObject({ system_name: 'Kamela', name: 'Knock Knock', date: '' })
    })

    it('returns blanks for text it cannot read', () => {
        expect(parse_selected_item_timer('')).toMatchObject({ name: '', date: '', time: '' })
        expect(parse_selected_item_timer('just words').date).toBe('')
    })
})

describe('eve_time_iso', () => {
    it('treats the date and time as EVE time', () => {
        expect(eve_time_iso('2026-11-22', '00:41:49')).toBe('2026-11-22T00:41:49.000Z')
        expect(eve_time_iso('2026-11-22', '00:41')).toBe('2026-11-22T00:41:00.000Z')
    })

    it('rejects missing or broken values', () => {
        expect(eve_time_iso('', '00:41')).toBeNull()
        expect(eve_time_iso('2026-13-40', '00:41')).toBeNull()
    })
})
