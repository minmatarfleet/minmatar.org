import { describe, expect, it } from 'vitest'
import { ping_preview_warning } from '@helpers/fetching/fleet_ping_preview'

describe('ping_preview_warning', () => {
    it('never warns for an alliance fleet', () => {
        expect(ping_preview_warning(false, false, null)).toBeNull()
    })

    it('warns when a group fleet has no channel to ping', () => {
        expect(ping_preview_warning(true, false, '<@&123>')).toBe('no_channel')
    })

    it('warns when a group fleet has a channel but no role to mention', () => {
        expect(ping_preview_warning(true, true, '')).toBe('no_role')
        expect(ping_preview_warning(true, true, undefined)).toBe('no_role')
    })

    it('is quiet when the ping reaches the group role', () => {
        // Even when the channel's name is unknown (Discord unreachable, not
        // cached yet): has_channel comes from the backend, and the ping goes out.
        expect(ping_preview_warning(true, true, '<@&123>')).toBeNull()
    })
})
