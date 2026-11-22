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
        expect(count('alpha_literal', { path: 'src/styles/properties/_colors.scss', text: ':root { --border-color: rgba(255, 255, 255, 0.06); }' })).toBe(0)
    })

    it('tint_off_ladder: literal percentages over transparent, not the ladder or other mixes', () => {
        expect(count('tint_off_ladder', astro(`<style>.a { background: color-mix(in srgb, var(--fleet-yellow) 12%, transparent); border-color: color-mix(in srgb, var(--faded, #666) 55%, transparent) }</style>`))).toBe(2)
        expect(count('tint_off_ladder', astro(`<style>.a { background: color-mix(in srgb, var(--fleet-yellow) var(--tint-soft), transparent); color: color-mix(in srgb, var(--green) 60%, var(--highlight)) }</style>`))).toBe(0)
    })

    it('retired_token: the retired custom properties, not class names', () => {
        expect(count('retired_token', astro(`<style>.a { color: var(--text-muted); border: 1px solid var(--hairline-strong); filter: drop-shadow(0 0 3px var(--glow)); background: var(--attention) }</style>`))).toBe(4)
        expect(count('retired_token', astro(`<style>.section-tab__meta--attention { color: var(--fleet-yellow); } .a { color: var(--attention-ish) }</style>`))).toBe(0)
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

    it('bespoke_empty_state: hand-styled empty classes, not states or the shared component', () => {
        expect(count('bespoke_empty_state', astro(`<style>.activity-empty { color: var(--faded) } .cm-empty, .cm-pager { margin: 0 }</style>`))).toBe(2)
        expect(count('bespoke_empty_state', astro(`<style lang="scss">.coords__empty { padding: 0 } .coords__empty-title { margin: 0 }</style>`))).toBe(2)
        expect(count('bespoke_empty_state', astro(`<style>.chip--empty { opacity: .5 } .day.is-empty { opacity: .6 } .slot:empty { display: none } .empty-state { color: red }</style>`))).toBe(0)
        expect(count('bespoke_empty_state', astro(`<p class="activity-empty">none</p>`))).toBe(0)
    })

    it('partial_error_state: data partials without ErrorRefetch or an explicit opt-out', () => {
        const partial = (text: string) => ({ path: 'src/pages/partials/x_component.astro', text })
        const fetches = "---\nimport { get_things } from '@helpers/api.minmatar.org/things'\n---\n"
        expect(count('partial_error_state', partial(fetches + '<div />'))).toBe(1)
        expect(count('partial_error_state', partial(fetches + '{fetch_error && <ErrorRefetch args={args} />}'))).toBe(0)
        expect(count('partial_error_state', partial(fetches.replace('---\n', '---\n// no-error-refetch: form result, errors render inline\n') + '<form />'))).toBe(0)
        expect(count('partial_error_state', partial('---\nimport { i18n } from "@helpers/i18n"\n---\n<div />'))).toBe(0)
        expect(count('partial_error_state', { path: 'src/components/blocks/Thing.astro', text: fetches })).toBe(0)
    })

    it('tailwind_apply: any @apply in styles', () => {
        expect(count('tailwind_apply', astro(`<style>.card { @apply p-4 bg-black; }</style>`))).toBe(1)
        expect(count('tailwind_apply', astro(`<p>Click apply to @apply</p>`))).toBe(0)
    })

    it('hand_rolled_action_menu: actions lists in a raw Dropdown or a bespoke popup, not ActionMenu or pickers', () => {
        expect(count('hand_rolled_action_menu', astro(`<Dropdown variant="button"><span slot="button">{t('actions')}</span><nav><button>Copy</button></nav></Dropdown>`))).toBe(1)
        expect(count('hand_rolled_action_menu', astro(`<div x-data="{ open: false }"><button x-on:click="open = !open" aria-haspopup="true" aria-label="Survey actions">⋯</button></div>`))).toBe(1)
        expect(count('hand_rolled_action_menu', astro(`<ActionMenu><ActionMenuItem href="/x">Open</ActionMenuItem></ActionMenu>`))).toBe(0)
        expect(count('hand_rolled_action_menu', astro(`<Dropdown><StationInfo slot="button" /><StationsSelector /></Dropdown>`))).toBe(0)
        expect(count('hand_rolled_action_menu', astro(`<button aria-haspopup="listbox" aria-label="Currency">LP</button><button aria-haspopup="true">{page_title}</button>`))).toBe(0)
        expect(count('hand_rolled_action_menu', astro(`<Dropdown><span slot="button">{t('actions')}</span></Dropdown>`, 'src/components/blocks/ActionMenu.astro'))).toBe(0)
    })

    it('raw_eve_image: EVE image URLs outside the helpers and Picture components', () => {
        expect(count('raw_eve_image', astro(`<img src="https://images.evetech.net/types/\${id}/icon?size=32" />`))).toBe(1)
        expect(count('raw_eve_image', { path: 'src/helpers/format.ts', text: 'const u = `//images.evetech.net/characters/${id}/portrait`' })).toBe(1)
        expect(count('raw_eve_image', { path: 'src/helpers/eve_image.ts', text: 'const u = `https://images.evetech.net/types/${id}/icon`' })).toBe(0)
        expect(count('raw_eve_image', astro(`<ItemPicture id={id} />`, 'src/components/blocks/ItemPicture.astro'))).toBe(0)
        expect(count('raw_eve_image', astro(`// the icons come from images.evetech.net\n<p>Served from images.evetech.net</p>`))).toBe(0)
    })

    it('raw_table: hand-written tables, not tablists or look-alike tags', () => {
        expect(count('raw_table', astro(`<table class="x"><tr><td>1</td></tr></table>`))).toBe(1)
        expect(count('raw_table', astro(`<div role="table"><div role="row"></div></div>`))).toBe(1)
        expect(count('raw_table', astro(`<tablet-x></tablet-x><div role="tablist"></div>`))).toBe(0)
        expect(count('raw_table', astro(`<style>[role="table"] { color: red }</style>`))).toBe(0)
        expect(count('raw_table', astro(`<table></table>`, 'src/components/blocks/DataGrid.astro'))).toBe(0)
    })

    it('overflow_x_scroll: overflow-x auto/scroll in CSS or Tailwind, not XFadeScroll or other axes', () => {
        expect(count('overflow_x_scroll', astro(`<style>.a { overflow-x: auto; }</style>`))).toBe(1)
        expect(count('overflow_x_scroll', astro(`<div class="[ x ] overflow-x-scroll"></div>`))).toBe(1)
        expect(count('overflow_x_scroll', astro(`<style>.b { overflow: auto; overflow-y: hidden; } .c { /* overflow-x: auto; */ }</style>`))).toBe(0)
        expect(count('overflow_x_scroll', astro(`<style>.d { overflow-x: hidden; }</style>`))).toBe(0)
        expect(count('overflow_x_scroll', { path: 'src/components/compositions/XFadeScroll.astro', text: '<style>.s { overflow-x: auto; }</style>' })).toBe(0)
        // pre blocks come from markdown and cannot be wrapped: exempt, however the selector nests them
        expect(count('overflow_x_scroll', astro(`<style>pre { overflow-x: auto; } .md :is(pre) { overflow-x: auto }</style>`))).toBe(0)
        expect(count('overflow_x_scroll', astro(`<style lang="scss">.a { :global(pre) { overflow-x: auto; } } .b { pre { padding: 0; overflow-x: scroll } }</style>`))).toBe(0)
        expect(count('overflow_x_scroll', astro(`<style>.pre-view { overflow-x: auto; } .prefix { overflow-x: auto }</style>`))).toBe(2)
        expect(count('overflow_x_scroll', astro(`<style lang="scss">pre { margin: 0 } .a { overflow-x: auto; }</style>`))).toBe(1)
    })

    it('direct_tippy: tippy() calls, not the component or property names', () => {
        expect(count('direct_tippy', astro(`---\n---\n<script>tippy(el, { content: 'x' })</script>`))).toBe(1)
        expect(count('direct_tippy', astro(`<div x-init="tippy($el, tippy_options)"></div>`))).toBe(1)
        expect(count('direct_tippy', astro(`<Tippy content="x"><span /></Tippy>`))).toBe(0)
        expect(count('direct_tippy', astro(`---\n---\n<script>this.tippy_options = {}; htmx.tippy_ready = true</script>`))).toBe(0)
        expect(count('direct_tippy', { path: 'src/helpers/swap_init.ts', text: 'tippy(el, opts)' })).toBe(0)
    })

    it('hand_rolled_tablist: element tablists, not the SectionTabs or a selector', () => {
        expect(count('hand_rolled_tablist', astro(`<div role="tablist" aria-label="x"></div>`))).toBe(1)
        expect(count('hand_rolled_tablist', astro(`<FlexInline role="tablist"><button role="tab" /></FlexInline>`))).toBe(1)
        expect(count('hand_rolled_tablist', astro(`<style>[role="tablist"] { gap: 0 }</style>`))).toBe(0)
        expect(count('hand_rolled_tablist', astro(`<div role="tab"></div>`))).toBe(0)
        expect(count('hand_rolled_tablist', astro(`<SectionTabs aria_label="x" />`))).toBe(0)
    })

    it('hand_rolled_popover: click-outside handlers in templates, not the popover components', () => {
        expect(count('hand_rolled_popover', astro(`<div x-on:click.outside="open = false"></div>`))).toBe(1)
        expect(count('hand_rolled_popover', astro(`<div @click.outside="open = false"></div>`))).toBe(1)
        expect(count('hand_rolled_popover', astro(`<div @click="open = !open"></div>`))).toBe(0)
        expect(count('hand_rolled_popover', astro(`---\nconst s = '@click.outside'\n---\n<div />`))).toBe(0)
        expect(count('hand_rolled_popover', astro(`<div x-on:click.outside="open = false"></div>`, 'src/components/blocks/Dropdown.astro'))).toBe(0)
    })

    it('raw_form_control: raw select/textarea/input, not hidden/submit/button inputs or the library controls', () => {
        expect(count('raw_form_control', astro(`<select name="x"><option>1</option></select>`))).toBe(1)
        expect(count('raw_form_control', astro(`<textarea name="note"></textarea>`))).toBe(1)
        expect(count('raw_form_control', astro(`<input type="checkbox" name="a" />`))).toBe(1)
        expect(count('raw_form_control', astro(`<input name="q" />`))).toBe(1)
        expect(count('raw_form_control', astro(`<input type="hidden" name="csrf" /><input type="submit" value="Save" /><input type="button" />`))).toBe(0)
        expect(count('raw_form_control', astro(`<input data-type="hidden" type="text" />`))).toBe(1)
        expect(count('raw_form_control', astro(`<Input type="text" /><Select /><Textarea />`))).toBe(0)
        expect(count('raw_form_control', astro(`<select name="x"></select>`, 'src/components/blocks/Select.astro'))).toBe(0)
    })

    it('raw_styled_button: raw button elements, not the Button family or look-alike tags', () => {
        expect(count('raw_styled_button', astro(`<button type="button">Save</button>`))).toBe(1)
        expect(count('raw_styled_button', astro(`<div><button class="x" /><button /></div>`))).toBe(2)
        expect(count('raw_styled_button', astro(`<Button variant="primary">Save</Button><StylessButton />`))).toBe(0)
        expect(count('raw_styled_button', astro(`<button-group></button-group><buttons-list />`))).toBe(0)
        expect(count('raw_styled_button', astro(`<button class="x">Go</button>`, 'src/components/blocks/Button.astro'))).toBe(0)
    })

    it('raw_chip: class tokens ending in chip/pill/chips, not names that only contain them', () => {
        expect(count('raw_chip', astro(`<span class="[ fleet-type-chip ]">Ship</span>`))).toBe(1)
        expect(count('raw_chip', astro(`<span class:list={['[ mk-sold-chip ]', active && 'is-on']}></span>`))).toBe(1)
        expect(count('raw_chip', astro(`<span class="[ spill ] chip-list chip__label"></span>`))).toBe(0)
        expect(count('raw_chip', astro(`<span class:list={[chip, 'x']}></span>`))).toBe(0)
        expect(count('raw_chip', astro(`<FilterChip label="x" /><Tag>y</Tag>`))).toBe(0)
        expect(count('raw_chip', astro(`<span class="[ x ]" class:list={['[ fleet-pill ]']}></span>`, 'src/components/blocks/Tag.astro'))).toBe(0)
    })

    it('hand_rolled_pager: hx-get URLs carrying a page parameter, not other query params', () => {
        expect(count('hand_rolled_pager', astro(`<button hx-get={\`/partials/x?page=\${page + 1}\`}></button>`))).toBe(1)
        expect(count('hand_rolled_pager', astro(`<div hx-get="/partials/x?page_num=2" hx-trigger="load"></div>`))).toBe(1)
        expect(count('hand_rolled_pager', astro(`<div hx-get="/partials/x?status=open"></div>`))).toBe(0)
        expect(count('hand_rolled_pager', astro(`<div hx-vals='{"page": 2}' hx-get="/partials/x"></div>`))).toBe(0)
        expect(count('hand_rolled_pager', astro(`<HtmxPager hx_get="/x?page=2" />`, 'src/components/blocks/HtmxPager.astro'))).toBe(0)
    })

    it('component_font: Google Fonts links and literal font-family, not the font tokens', () => {
        expect(count('component_font', { path: 'src/styles/_global.scss', text: "@import url('https://fonts.googleapis.com/css2?family=Inter');" }) ).toBe(1)
        expect(count('component_font', astro(`<style>body { font-family: Inter, sans-serif; }</style>`))).toBe(1)
        expect(count('component_font', astro(`<style>body { font-family: var(--default-font); } h1 { font-family: inherit }</style>`))).toBe(0)
        expect(count('component_font', astro(`<style>.a { font-family: var(--x), sans-serif; } /* font-family: Arial; */ $font-family: 'Inter';</style>`))).toBe(0)
        expect(count('component_font', { path: 'src/styles/_fonts.scss', text: "@font-face { font-family: 'Norwester'; }" }) ).toBe(0)
    })

    it('palette_off_meaning: security-status and meta-group tokens outside the components that own them', () => {
        expect(count('palette_off_meaning', astro(`<span style="color: var(--security-status-1)"></span>`))).toBe(1)
        expect(count('palette_off_meaning', astro(`<style>.x { color: var(--tech-ii); }</style>`))).toBe(1)
        expect(count('palette_off_meaning', astro(`<style>.x { color: var(--faction-color); } .y { color: var(--highlight) }</style>`))).toBe(0)
        expect(count('palette_off_meaning', astro(`<style>.x { color: var(--security-status-1) }</style>`, 'src/components/blocks/sde/SecurityStatus.astro'))).toBe(0)
        expect(count('palette_off_meaning', { path: 'src/styles/_global.scss', text: '.text-status-1 { color: var(--security-status-1) !important; }\n.other { color: var(--security-status-1) }' })).toBe(1)
    })

    it('local_semantic_colour: component-local semantic colour definitions, not tokens that read them', () => {
        expect(count('local_semantic_colour', astro(`<style>.a { --hp-warn: #c04a1f; }</style>`))).toBe(1)
        expect(count('local_semantic_colour', astro(`<style>.a { --bar-good: green; --status-danger: red; }</style>`))).toBe(2)
        expect(count('local_semantic_colour', astro(`<style>.a { --x-warning: red; }</style>`))).toBe(1)
        expect(count('local_semantic_colour', astro(`<style>.a { color: var(--hp-warn); --warn-color: red; border-color: var(--fleet-warn-bg) }</style>`))).toBe(0)
        expect(count('local_semantic_colour', { path: 'src/styles/properties/_colors.scss', text: ':root { --alliance-good: #3a7; }' })).toBe(0)
    })
})
