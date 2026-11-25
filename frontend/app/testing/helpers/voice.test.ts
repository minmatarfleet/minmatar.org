import { describe, expect, it } from 'vitest'
import {
    parse_character_id, parse_wings, new_login_state, login_state_matches,
    detect_device, voice_step, parse_voice_view, parse_since, connected_since,
} from '@helpers/voice_session'
import { posted_voice_option, posted_voice_fields } from '@helpers/fetching/voice_options'
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

    it('posted_voice_fields sends only the fields the picked option posted', () => {
        expect(posted_voice_fields(new FormData())).toEqual({})
        const discord = new FormData()
        discord.set('voice_option_id', '1')
        discord.set('voice_channel_id', '1213929683603951696')
        expect(posted_voice_fields(discord)).toEqual({ voice_channel_id: '1213929683603951696' })
        const mumble = new FormData()
        mumble.set('voice_option_id', '2')
        mumble.set('mumble_open', 'restricted')
        expect(posted_voice_fields(mumble)).toEqual({ mumble_open: false })
    })

    it('voice_login_url encodes where EVE sends the pilot back, and the state', () => {
        const url = voice_login_url('https://my.minmatar.org/voice/login', 'abc_DEF-123')
        expect(url.endsWith('/api/voice/login?redirect_url=https%3A%2F%2Fmy.minmatar.org%2Fvoice%2Flogin&state=abc_DEF-123')).toBe(true)
    })

    it('new_login_state is long, URL-safe and different every time', () => {
        const a = new_login_state()
        const b = new_login_state()
        expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/)
        expect(a).not.toBe(b)
    })

    it('login_state_matches needs the state this browser started with', () => {
        const state = new_login_state()
        expect(login_state_matches(state, state)).toBe(true)
        expect(login_state_matches(state, new_login_state())).toBe(false)
        expect(login_state_matches(state, undefined)).toBe(false)
        expect(login_state_matches(null, state)).toBe(false)
        expect(login_state_matches('', '')).toBe(false)
    })
})

describe('voice flow helpers', () => {
    it('detect_device reads the user agent, Windows when unsure', () => {
        expect(detect_device('Mozilla/5.0 (Windows NT 10.0; Win64; x64)')).toBe('windows')
        expect(detect_device('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4)')).toBe('macos')
        expect(detect_device('Mozilla/5.0 (X11; Linux x86_64)')).toBe('linux')
        expect(detect_device('Mozilla/5.0 (Linux; Android 14; Pixel 8)')).toBe('android')
        expect(detect_device('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X)')).toBe('ios')
        expect(detect_device(null)).toBe('windows')
    })

    it('voice_step: refusals first, then setup until the first connection', () => {
        const status = { banned: false, admitted: true, reason: 'ok', certificate_count: 0 }
        expect(voice_step(status)).toBe('setup')
        expect(voice_step({ ...status, certificate_count: 2 })).toBe('ready')
        expect(voice_step({ ...status, admitted: false, reason: 'no_access' })).toBe('waiting')
        expect(voice_step({ ...status, admitted: false, reason: 'not_main' })).toBe('not_main')
        expect(voice_step({ ...status, admitted: false, banned: true, reason: 'banned' })).toBe('banned')
    })

    it('parse_voice_view takes the known views only', () => {
        expect(parse_voice_view('keys')).toBe('keys')
        expect(parse_voice_view('setup')).toBe('setup')
        expect(parse_voice_view('trouble')).toBe('trouble')
        expect(parse_voice_view('admin')).toBeNull()
        expect(parse_voice_view(null)).toBeNull()
    })

    it('parse_since keeps a recent Connect only', () => {
        const now = new Date('2026-11-24T19:00:00Z')
        expect(parse_since('2026-11-24T18:59:00Z', now)?.toISOString()).toBe('2026-11-24T18:59:00.000Z')
        expect(parse_since('2026-11-24T18:50:00Z', now)).toBeNull()
        expect(parse_since('not a date', now)).toBeNull()
    })

    it('connected_since sees a certificate bound or used after Connect', () => {
        const since = new Date('2026-11-24T19:00:00Z')
        const old = { created_at: '2026-10-01T00:00:00Z', last_used_at: '2026-11-20T00:00:00Z' }
        expect(connected_since([old], since)).toBe(false)
        expect(connected_since([old, { created_at: '2026-11-24T19:00:30Z', last_used_at: null }], since)).toBe(true)
        expect(connected_since([{ ...old, last_used_at: '2026-11-24T18:59:55Z' }], since)).toBe(true)
        expect(connected_since([], since)).toBe(false)
    })
})
