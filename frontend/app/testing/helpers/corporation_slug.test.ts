import { describe, expect, it } from 'vitest'
import { corporation_path, corporation_slug } from '@helpers/corporations/detail'

describe('corporation slugs', () => {
    it('matches the backend slug rules', () => {
        expect(corporation_slug('Rattini Tribe')).toBe('rattini-tribe')
        expect(corporation_slug('Every Little Helps.')).toBe('every-little-helps')
        expect(corporation_slug("Shea'en M'Taal")).toBe('shea-en-m-taal')
    })

    it('falls back to the ID when a name has no usable characters', () => {
        expect(corporation_path(98726134, 'Rattini Tribe')).toBe('/alliance/corporations/rattini-tribe/')
        expect(corporation_path(123, '...')).toBe('/alliance/corporations/123/')
        expect(corporation_path(123, null)).toBe('/alliance/corporations/123/')
    })
})
