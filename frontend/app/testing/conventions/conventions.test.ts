// Conventions ratchet for .claude/rules/frontend-design.md (see rules.ts).
//
// Failing here means a change added a violation. Fix the code. If the new hit
// is genuinely unavoidable, regenerate the baseline and justify it in the PR:
//
//   UPDATE_CONVENTIONS_BASELINE=1 npx vitest run testing/conventions
//
// Lowering a count never fails; regenerate the baseline to lock the gain in.

import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { RULES, Z_INDEX_LAYER_THRESHOLD, rule, type ConventionRule } from './rules'
import { APP_ROOT, source_files, type Hit, type SourceFile } from './scan'

type Baseline = Record<string, Record<string, number>>

const BASELINE_PATH = join(APP_ROOT, 'testing/conventions/baseline.json')

function scan(r: ConventionRule): Map<string, Hit[]> {
    const by_file = new Map<string, Hit[]>()
    for (const file of source_files()) {
        const hits = r.find(file)
        if (hits.length) by_file.set(file.path, hits)
    }
    return by_file
}

function describe_hits(path: string, hits: Hit[]): string {
    return hits.map((h) => `    ${path}:${h.line}  ${h.snippet}`).join('\n')
}

const results = new Map(RULES.map((r) => [r.id, scan(r)]))

if (process.env.UPDATE_CONVENTIONS_BASELINE) {
    const next: Baseline = {}
    for (const r of RULES.filter((r) => r.kind === 'ratchet')) {
        next[r.id] = Object.fromEntries([...results.get(r.id)!].map(([path, hits]) => [path, hits.length]))
    }
    writeFileSync(BASELINE_PATH, JSON.stringify(next, null, 4) + '\n')
}

const baseline: Baseline = JSON.parse(readFileSync(BASELINE_PATH, 'utf8'))

describe('frontend conventions', () => {
    it('baseline.json only holds ratchet rules', () => {
        const ratchet_ids = RULES.filter((r) => r.kind === 'ratchet').map((r) => r.id).sort()
        expect(Object.keys(baseline).sort()).toEqual(ratchet_ids)
    })

    for (const r of RULES) {
        if (r.kind === 'absolute') {
            it(`${r.id}: no violations`, () => {
                const found = [...results.get(r.id)!]
                const report = found.map(([path, hits]) => describe_hits(path, hits)).join('\n')
                expect(found.length, `${r.why}\n${report}`).toBe(0)
            })
            continue
        }

        it(`${r.id}: no file exceeds its baseline`, () => {
            const allowed = baseline[r.id] ?? {}
            const over: string[] = []
            for (const [path, hits] of results.get(r.id)!) {
                const limit = allowed[path] ?? 0
                if (hits.length > limit) over.push(`  ${path}: ${hits.length} (allowed ${limit})\n${describe_hits(path, hits)}`)
            }
            expect(over, `${r.why}\nNew violations:\n${over.join('\n')}`).toEqual([])
        })
    }
})

// Precision checks: each matcher fires on the pattern it targets and stays quiet on look-alikes.
const astro = (text: string, path = 'src/components/blocks/Fixture.astro'): SourceFile => ({ path, text })
const count = (id: string, file: SourceFile) => rule(id).find(file).length

describe('convention rule matchers', () => {
    it('client_fetch: client code only, not the server frontmatter', () => {
        expect(count('client_fetch', astro(`---\nconst r = await fetch(url)\n---\n<div />`))).toBe(0)
        expect(count('client_fetch', astro(`---\n---\n<div x-data="{ load() { fetch('/api/x') } }"></div>`))).toBe(1)
        expect(count('client_fetch', astro(`---\n---\n<script>axios.get('/x')</script>`))).toBe(1)
        expect(count('client_fetch', astro(`---\n---\n<div hx-get="/partials/x" hx-trigger="load"></div>`))).toBe(0)
    })

    it('inner_html: building DOM fails, clearing it does not', () => {
        expect(count('inner_html', astro(`---\n---\n<script>el.innerHTML = '<li>' + name + '</li>'</script>`))).toBe(1)
        expect(count('inner_html', astro(`---\n---\n<script>el.insertAdjacentHTML('beforeend', html)</script>`))).toBe(1)
        expect(count('inner_html', astro(`---\n---\n<script>el.innerHTML = ''\nlist.innerHTML = "";</script>`))).toBe(0)
        expect(count('inner_html', astro(`---\n---\n<script>if (el.innerHTML === '') {}</script>`))).toBe(0)
    })

    it('z_index_layer: only layer-sized literals', () => {
        expect(count('z_index_layer', astro(`<style>.a { z-index: 1000; }</style>`))).toBe(1)
        expect(count('z_index_layer', astro(`<div class="z-[9999]"></div>`))).toBe(1)
        expect(count('z_index_layer', astro(`<style>.a { z-index: ${Z_INDEX_LAYER_THRESHOLD - 1}; } .b { z-index: var(--dialog-z-index); }</style>`))).toBe(0)
        expect(count('z_index_layer', { path: 'src/styles/properties/_z-index.scss', text: ':root { --base-z-index: 10000; z-index: 10000; }' })).toBe(0)
    })

    it('hex_colour: declarations, not selectors, url() fragments or token fallbacks', () => {
        expect(count('hex_colour', astro(`<style>.a { color: #fff; border: 1px solid #b53620 }</style>`))).toBe(2)
        expect(count('hex_colour', astro(`<div style="color:#fff"></div>`))).toBe(1)
        expect(count('hex_colour', astro(`<div class="bg-[#121212]"></div>`))).toBe(1)
        expect(count('hex_colour', astro(`<style>a:hover #add { color: var(--highlight); } .b { mask: url(#fade); color: var(--fleet-red, #b53620); }</style>`))).toBe(0)
        expect(count('hex_colour', { path: 'src/styles/properties/_colors.scss', text: ':root { --fleet-red: #b53620; }' })).toBe(0)
    })

    it('is_superuser_read: reads, not type declarations or gates.ts', () => {
        expect(count('is_superuser_read', astro(`---\nconst is_superuser = user?.is_superuser\n---`))).toBe(1)
        expect(count('is_superuser_read', { path: 'src/types/jwt.ts', text: 'export interface User { is_superuser: boolean }' })).toBe(0)
        expect(count('is_superuser_read', { path: 'src/helpers/gates.ts', text: 'Boolean(user.is_superuser)' })).toBe(0)
    })

    it('t_as_any: casts inside t(), not elsewhere', () => {
        expect(count('t_as_any', astro('{t(`burst_kind_${kind}` as any)}'))).toBe(1)
        expect(count('t_as_any', astro('{t(key as any)}'))).toBe(1)
        expect(count('t_as_any', astro("{t(t_key('burst_kind_', kind))} {format(x as any)} {at(i as any)}"))).toBe(0)
    })

    it('cdn_unpinned: exact versions only', () => {
        const tag = (url: string) => astro(`<script src="${url}"></script>`)
        expect(count('cdn_unpinned', tag('https://cdn.jsdelivr.net/npm/flatpickr'))).toBe(1)
        expect(count('cdn_unpinned', tag('https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js'))).toBe(1)
        expect(count('cdn_unpinned', tag('https://cdn.jsdelivr.net/npm/@justinribeiro/lite-youtube@1/lite-youtube.min.js'))).toBe(1)
        expect(count('cdn_unpinned', tag('https://unpkg.com/htmx.org'))).toBe(1)
        expect(count('cdn_unpinned', tag('https://cdn.jsdelivr.net/npm/swiper@11.2.10/swiper-bundle.min.js'))).toBe(0)
        expect(count('cdn_unpinned', tag('https://cdn.jsdelivr.net/npm/@alpinejs/mask@3.16.0/dist/cdn.min.js'))).toBe(0)
        expect(count('cdn_unpinned', tag('https://unpkg.com/htmx.org@1.9.10'))).toBe(0)
        expect(count('cdn_unpinned', tag('https://cdnjs.cloudflare.com/ajax/libs/pako/2.0.4/pako.min.js'))).toBe(0)
    })

    it('alpha_literal: white/black alpha in CSS, not tokens, fallbacks, other colours or scripts', () => {
        expect(count('alpha_literal', astro(`<style>.a { border: 1px solid rgba(255, 255, 255, 0.06); background: rgba(0,0,0,.7) }</style>`))).toBe(2)
        expect(count('alpha_literal', astro(`<div style="color: rgb(255 255 255 / 0.5)"></div>`))).toBe(1)
        expect(count('alpha_literal', astro(`<style>.a { color: var(--border-color, rgba(255, 255, 255, 0.1)); mask: linear-gradient(rgb(0,0,0) 0%, transparent); background: rgba(85, 85, 85, 0.1) }</style>`))).toBe(0)
        expect(count('alpha_literal', astro(`---\n---\n<script>chart.color = 'rgba(255, 255, 255, 0.5)'</script>`))).toBe(0)
        expect(count('alpha_literal', { path: 'src/styles/properties/_colors.scss', text: ':root { --hairline: rgba(255, 255, 255, 0.06); }' })).toBe(0)
    })

    it('skeleton_keyframes: per-component skeleton keyframes, not the shared ones', () => {
        expect(count('skeleton_keyframes', astro(`<style>@keyframes market-contracts-skel { 0% { opacity: 1 } }</style>`))).toBe(1)
        expect(count('skeleton_keyframes', astro(`<style>@keyframes shimmer { 0% { opacity: 1 } }</style>`))).toBe(1)
        expect(count('skeleton_keyframes', astro(`<style>@keyframes rotation { 0% { opacity: 1 } } .s { animation: skeleton-shimmer 1s }</style>`))).toBe(0)
        expect(count('skeleton_keyframes', { path: 'src/styles/_animations.scss', text: '@keyframes skeleton-shimmer { 0% { opacity: 1 } }' })).toBe(0)
    })

    it('hover_motion_ungated: hover transforms outside @media (hover: hover)', () => {
        expect(count('hover_motion_ungated', astro(`<style>.a:hover { transform: scale(1.05); }</style>`))).toBe(1)
        expect(count('hover_motion_ungated', astro(`<style lang="scss">.a { &:hover, &:focus-visible { color: red; transform: translateX(2px) } }</style>`))).toBe(1)
        expect(count('hover_motion_ungated', astro(`<style lang="scss">.card:hover { picture img { scale: 1.1 } }</style>`))).toBe(1)
        expect(count('hover_motion_ungated', { path: 'src/styles/_global.scss', text: '.c { &:hover { img { transform: scale(1.1) } } }' })).toBe(1)
        // gated (directly or by an ancestor), focus-only, non-hover, none and the centring idiom are fine
        expect(count('hover_motion_ungated', astro(`<style lang="scss">@media (hover: hover) { .a:hover { transform: scale(1.05) } } .b { @media (hover: hover) { &:hover { transform: scale(1.05) } } }</style>`))).toBe(0)
        expect(count('hover_motion_ungated', astro(`<style>.a:focus-visible { transform: scale(1.05) } .b { transform: rotate(180deg) } .c:disabled:hover { transform: none }</style>`))).toBe(0)
        expect(count('hover_motion_ungated', astro(`<style lang="scss">.a:hover { &::before { left: 50%; transform: translateX(-50%) } } /* .x:hover { transform: scale(2) } */</style>`))).toBe(0)
        expect(count('hover_motion_ungated', astro(`<style>@media (hover: none) { .a:active { transform: scale(0.95) } }</style>`))).toBe(0)
    })

    it('tailwind_apply: any @apply in styles', () => {
        expect(count('tailwind_apply', astro(`<style>.card { @apply p-4 bg-black; }</style>`))).toBe(1)
        expect(count('tailwind_apply', astro(`<p>Click apply to @apply</p>`))).toBe(0)
    })
})
