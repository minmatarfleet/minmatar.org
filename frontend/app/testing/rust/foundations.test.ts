// Foundations completeness: every token, font, theme mode and UI scale the app
// defines shows up in Rust, the fonts it imports load in Storybook, and
// rust/public/tokens.json (the DTCG export) matches the stylesheets.
import { describe, expect, test } from 'vitest'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render_component } from './render_story'
import { read_tokens, read_font_families, read_theme_overrides, read_ui_scales, to_dtcg, app_sources } from '../../rust/foundations/tokens'
import ColorTokens from '../../rust/components/foundations/ColorTokens.astro'
import TypeSpecimen from '../../rust/components/foundations/TypeSpecimen.astro'
import SpaceScale from '../../rust/components/foundations/SpaceScale.astro'
import MotionLayers from '../../rust/components/foundations/MotionLayers.astro'
import ThemeModes from '../../rust/components/foundations/ThemeModes.astro'

const APP = resolve(__dirname, '../..')

describe('Rust foundations', () => {
    test('every colour token is on the Colors page', async () => {
        const html = await render_component(ColorTokens, {}, {})
        const colors = read_tokens().filter((t) => t.kind === 'color')
        expect(colors.length).toBeGreaterThan(50)
        for (const token of colors)
            expect(html, token.name).toContain(`data-token="${token.name}"`)
    })

    test('every font family is on the Typography page', async () => {
        const html = await render_component(TypeSpecimen, { show_system: true }, {})
        const families = read_font_families()
        for (const family of families)
            expect(html, family.family).toContain(`data-family="${family.family}"`)
        for (const expected of ['Norwester', 'Montserrat Variable', 'Qahiri', 'Orbitron', 'Source Sans 3', 'Lora'])
            expect(families.map((f) => f.family)).toContain(expected)
    })

    test('every Google Font the app imports is loaded in Storybook', () => {
        const head = readFileSync(resolve(APP, '.storybook/preview-head.html'), 'utf8')
        const google = read_font_families().filter((f) => f.source === 'google-fonts')
        expect(google.length).toBeGreaterThan(0)
        for (const font of google)
            expect(head, `${font.family} is missing from .storybook/preview-head.html`).toContain(`family=${font.family.replace(/ /g, '+')}`)
    })

    test('every fontsource package the app imports is imported by the preview', () => {
        const preview = readFileSync(resolve(APP, '.storybook/preview.ts'), 'utf8')
        const packages = new Set(app_sources().flatMap(({ text }) => [...text.matchAll(/import\s+['"](@fontsource[^'"]+)['"]/g)].map((m) => m[1])))
        expect(packages.size).toBeGreaterThan(0)
        for (const pkg of packages)
            expect(preview, `${pkg} is missing from .storybook/preview.ts`).toContain(pkg)
    })

    test('every space, layout, motion and layer token is shown', async () => {
        const space = await render_component(SpaceScale, {}, {})
        const motion = await render_component(MotionLayers, {}, {})
        for (const token of read_tokens()) {
            if (token.kind === 'space' || token.kind === 'size')
                expect(space, token.name).toContain(`data-token="${token.name}"`)
            if (token.kind === 'transition' || token.kind === 'z-index')
                expect(motion, token.name).toContain(`data-token="${token.name}"`)
        }
    })

    test('every theme mode and UI scale is shown and in the toolbar', async () => {
        const modes = await render_component(ThemeModes, {}, {})
        const scales = await render_component(ThemeModes, { mode: 'scales' }, {})
        const overrides = read_theme_overrides()
        expect(overrides.map((o) => o.selector)).toContain('body.color-blind-mode')
        for (const override of overrides)
            expect(modes).toContain(`data-theme="${override.selector}"`)
        const preview = readFileSync(resolve(APP, '.storybook/preview.ts'), 'utf8')
        for (const scale of read_ui_scales()) {
            expect(scales).toContain(`data-scale="${scale}"`)
            expect(preview).toContain(`'${scale}'`)
        }
    })

    test('rust/public/tokens.json matches the stylesheets (UPDATE_TOKENS=1 rewrites it)', () => {
        const path = resolve(APP, 'rust/public/tokens.json')
        const expected = JSON.stringify(to_dtcg(), null, 2) + '\n'
        if (process.env.UPDATE_TOKENS)
            writeFileSync(path, expected)
        expect(readFileSync(path, 'utf8'), 'run UPDATE_TOKENS=1 npx vitest run testing/rust/foundations.test.ts').toBe(expected)
    })
})
