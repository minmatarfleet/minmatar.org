// Every `var(--x)` without a fallback must resolve to a custom property that
// something in src/ defines. An undefined one does not fail loudly: the
// declaration becomes invalid at computed-value time and the property silently
// inherits or resets (Button.astro used `var(--step--0)` for two years, so
// every button inherited its font size).
//
// Definitions are collected generously (any `--name:` in any file, define:vars
// keys, style.setProperty) so a hit here is always a real typo or a token that
// was never added.

import { describe, expect, it } from 'vitest'

import { line_at, source_files, type SourceFile } from './scan'

export function defined_properties(files: SourceFile[]): Set<string> {
    const defined = new Set<string>()
    for (const { text } of files) {
        // CSS declarations, inline styles, object keys ('--x': ...) and Tailwind [--x:...] arbitrary properties.
        for (const m of text.matchAll(/(--[A-Za-z0-9_-]+)['"`]?\s*:/g)) defined.add(m[1])
        for (const m of text.matchAll(/setProperty\(\s*['"`](--[A-Za-z0-9_-]+)/g)) defined.add(m[1])
        // <style define:vars={{ width, font_size: size }}> defines --width and --font_size.
        for (const m of text.matchAll(/define:vars=\{\{([\s\S]*?)\}\}/g)) {
            for (const key of m[1].matchAll(/(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?=[,:]|$)/g)) defined.add(`--${key[1]}`)
        }
    }
    return defined
}

export function undefined_references(files: SourceFile[]): string[] {
    const defined = defined_properties(files)
    const problems: string[] = []
    for (const file of files) {
        // Only fallback-less references: var(--x, something) renders the fallback.
        for (const m of file.text.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*\)/g)) {
            if (!defined.has(m[1])) problems.push(`${file.path}:${line_at(file.text, m.index!)}  ${m[0]}`)
        }
    }
    return problems
}

describe('CSS custom properties', () => {
    it('every var(--x) without a fallback is defined somewhere in src/', () => {
        const problems = undefined_references(source_files())
        expect(problems, `Undefined custom properties (typo, or a token missing from src/styles/properties):\n${problems.join('\n')}`).toEqual([])
    })

    it('flags typos and missing tokens, not fallbacks or locally defined properties', () => {
        const file = (path: string, text: string): SourceFile => ({ path, text })
        const tokens = file('src/styles/properties/_font-sizes.scss', ':root { --step-0: 1rem; }')
        const problems = undefined_references([
            tokens,
            file('src/components/blocks/A.astro', '<style>button { font-size: var(--step--0); }</style>'),
            file('src/components/blocks/B.astro', '<style>button { font-size: var(--step-0); color: var(--muted-color, var(--step-0)); }</style>'),
            file('src/components/blocks/C.astro', '<style define:vars={{ width, font_size: size }}>.c { width: var(--width); font-size: var(--font_size); }</style>'),
            file('src/components/blocks/D.astro', `<div style={{ '--progress': '50%' }} class="w-[var(--progress)]"></div>`),
        ])
        expect(problems).toEqual(['src/components/blocks/A.astro:1  var(--step--0)'])
    })
})
