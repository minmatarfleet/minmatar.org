import { describe, expect, it } from 'vitest'
import { parse_structure_action, tribe_page_path } from '@helpers/tribe_structure'

const params = (query: string) => new URLSearchParams(query)

describe('tribe structure routing', () => {
    it('reads each mode with the ids it needs', () => {
        expect(parse_structure_action(params('action=new_tribe'))).toEqual({ mode: 'new_tribe', tribe_id: null, group_id: null })
        expect(parse_structure_action(params('action=new_group&tribe_id=4'))).toEqual({ mode: 'new_group', tribe_id: 4, group_id: null })
        expect(parse_structure_action(params('action=rename&tribe_id=4&group_id=9'))).toEqual({ mode: 'rename', tribe_id: 4, group_id: 9 })
        expect(parse_structure_action(params('action=archive&tribe_id=4'))).toEqual({ mode: 'archive', tribe_id: 4, group_id: null })
        expect(parse_structure_action(params('action=restore&tribe_id=4&group_id=9'))?.mode).toBe('restore')
    })

    it('refuses unknown modes and missing or bad ids', () => {
        expect(parse_structure_action(params('action=delete&tribe_id=4'))).toBeNull()
        expect(parse_structure_action(params(''))).toBeNull()
        expect(parse_structure_action(params('action=rename'))).toBeNull()
        expect(parse_structure_action(params('action=archive&tribe_id=-1'))).toBeNull()
        expect(parse_structure_action(params('action=new_group&tribe_id=4&group_id=9'))).toBeNull()
    })

    it('ignores a group id on a new tribe', () => {
        expect(parse_structure_action(params('action=new_tribe&tribe_id=4&group_id=9'))).toEqual({ mode: 'new_tribe', tribe_id: 4, group_id: null })
    })

    it('links the tribe or group page', () => {
        expect(tribe_page_path(4)).toBe('/alliance/tribes/4')
        expect(tribe_page_path(4, 9)).toBe('/alliance/tribes/4/9')
    })
})
