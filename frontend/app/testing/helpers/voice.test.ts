import { describe, expect, it } from 'vitest'
import { parse_character_id, parse_wings } from '@helpers/voice_session'
import { posted_voice_option } from '@helpers/fetching/voice_options'
import { voice_login_url } from '@helpers/api.minmatar.org/voice'

describe('voice helpers', () => {
    it('parse_character_id takes positive integers only', () => {
        expect(parse_character_id('2112345678')).toBe(2112345678)
        expect(parse_character_id(' 42 ')).toBe(42)
        expect(parse_character_id('0')).toBeNull()
        expect(parse_character_id('-5')).toBeNull()
        expect(parse_character_id('abc')).toBeNull()
        expect(parse_character_id(null)).toBeNull()
    })

    it('parse_wings reads one wing per line and skips the rest', () => {
        expect(parse_wings('1234 = Auxiliary A\n\n5678=Logistics\nnot a line')).toEqual({
            '1234': 'Auxiliary A',
            '5678': 'Logistics',
        })
        expect(parse_wings('')).toEqual({})
    })

    it('posted_voice_option leaves the option alone without a picker', () => {
        const without = new FormData()
        expect(posted_voice_option(without)).toBeUndefined()
        const picked = new FormData()
        picked.set('voice_option_id', '7')
        expect(posted_voice_option(picked)).toBe(7)
    })

    it('voice_login_url encodes where EVE sends the pilot back', () => {
        const url = voice_login_url('https://my.minmatar.org/voice/login')
        expect(url.endsWith('/api/voice/login?redirect_url=https%3A%2F%2Fmy.minmatar.org%2Fvoice%2Flogin')).toBe(true)
    })
})
