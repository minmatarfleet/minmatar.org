import { describe, expect, it } from 'vitest'
import { doctrine_path, fitting_path, fitting_render_path, id_slug, name_slug } from '@helpers/ship_paths'

describe('ship paths', () => {
    it('slugs fitting and doctrine names', () => {
        expect(name_slug('[FL33T] Torpedo Typhoon Fleet Issue')).toBe('fl33t-torpedo-typhoon-fleet-issue')
        expect(name_slug('TFIs')).toBe('tfis')
        expect(name_slug("[NVY] 'Vehemence' Smartbomb Thrasher")).toBe('nvy-vehemence-smartbomb-thrasher')
    })

    it('cuts long names at a word boundary', () => {
        const slug = name_slug('Very Long Fitting Name '.repeat(10))
        expect(slug.length).toBeLessThanOrEqual(80)
        expect(slug.endsWith('-')).toBe(false)
        expect('very-long-fitting-name-'.repeat(10)).toContain(slug)
    })

    it('leads with the ID so the page can parse it and falls back to the bare ID', () => {
        expect(id_slug(444, 'Torpedo Typhoon')).toBe('444-torpedo-typhoon')
        expect(parseInt(id_slug(444, 'Torpedo Typhoon'))).toBe(444)
        expect(parseInt(id_slug(444, '123 Rifters'))).toBe(444)
        expect(id_slug(444, '...')).toBe('444')
        expect(id_slug(444, null)).toBe('444')
        expect(id_slug(444)).toBe('444')
    })

    it('builds the canonical detail URLs', () => {
        expect(fitting_path(8, '[FL33T] Burst')).toBe('/ships/fittings/normal/8-fl33t-burst/')
        expect(fitting_render_path(8, '[FL33T] Burst')).toBe('/ships/fittings/render/8-fl33t-burst/')
        expect(fitting_path(8)).toBe('/ships/fittings/normal/8/')
        expect(doctrine_path(13, 'TFIs')).toBe('/ships/doctrines/13-tfis/')
    })
})
