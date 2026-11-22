import { describe, expect, it } from 'vitest'
import { external_link_attributes } from '@helpers/external_link'

const build = (overrides: Partial<Parameters<typeof external_link_attributes>[0]> = {}) =>
    external_link_attributes({
        href: 'https://example.com/',
        title: 'Leaving the website',
        partial: '/partials/external_link_disclaimer_dialog/',
        ...overrides,
    })

describe('external_link_attributes', () => {
    it('JSON-encodes a title containing a quote', () => {
        const { x_data } = build({ title: "You're leaving" })
        expect(x_data).toContain(`title: "You're leaving"`)
        expect(() => new Function(`return ${x_data.replace('$persist(false)', 'false')}`)).not.toThrow()
    })

    it('JSON-encodes an href containing a quote', () => {
        const { x_data, x_on_click_prevent } = build({ href: "https://example.com/it's" })
        expect(x_data).toContain(`accept_href: "https://example.com/it's"`)
        expect(x_on_click_prevent).toContain(`window.open("https://example.com/it's", '_blank')`)
    })

    it('escapes double quotes and backslashes', () => {
        const { x_data } = build({ title: 'a "b" \\ c' })
        expect(x_data).toContain('title: "a \\"b\\" \\\\ c"')
    })

    it('keeps the caller x-data members after the disclaimer members', () => {
        const { x_data } = build({ x_data_elements: ' pinned: false ' })
        expect(x_data).toMatch(/\},\s+pinned: false\s+\}$/)
    })

    it('adds no trailing comma without caller members', () => {
        expect(build().x_data).not.toMatch(/,\s*\}$/)
    })
})
