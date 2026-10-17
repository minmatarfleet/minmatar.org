// The machine-checked subset of .claude/rules/frontend-design.md.
//
// `ratchet` rules have existing offenders: baseline.json holds the allowed
// count per file, and a file may only go down. `absolute` rules have no
// offenders left, so any hit fails. When a ratchet rule's baseline reaches
// zero, move it to `absolute` and drop its key from baseline.json.
//
// Keep every rule narrow enough that a hit is always a real violation.

import { astro_template, css_regions, hits_in, type Hit, type SourceFile } from './scan'

export interface ConventionRule {
    id: string
    kind: 'ratchet' | 'absolute'
    /** What the rule protects and what to do instead; printed on failure. */
    why: string
    find: (file: SourceFile) => Hit[]
}

const is_astro = (file: SourceFile) => file.path.endsWith('.astro')
const is_script = (file: SourceFile) => /\.(ts|js|mjs)$/.test(file.path)

/** Template + client-script part of .astro files, and plain TS/JS modules. */
const code_regions = (file: SourceFile) => {
    if (is_astro(file)) return [astro_template(file.text)]
    if (is_script(file)) return [{ text: file.text, offset: 0 }]
    return []
}

/** Hex colour inside a CSS value. `var(--token, #hex)` fallbacks are skipped: the token is what renders. */
const HEX_IN_DECLARATION = /(?:^|[;{])\s*(--[\w-]+|[a-z-]+)\s*:([^;{}]*)(?=[;}]|$)/g
const HEX = /#[0-9a-fA-F]{3,8}\b/g
const VAR_HEX_FALLBACK = /var\(\s*--[\w-]+\s*,\s*#[0-9a-fA-F]{3,8}\s*\)/g
const URL_FUNCTION = /url\([^)]*\)/g
const value_has_hex = (value: string) => [...value.replace(URL_FUNCTION, '').replace(VAR_HEX_FALLBACK, '').matchAll(HEX)].length > 0

/** rgba()/rgb() of pure white or black with an alpha: rgba(255, 255, 255, 0.06), rgb(0 0 0 / 0.5). */
const ALPHA_LITERAL = /rgba?\(\s*(?:255[\s,]+255[\s,]+255|0[\s,]+0[\s,]+0)\s*[,/]\s*[\d.]+%?\s*\)/g
/** `var(--token, rgba(...))`: the fallback never renders while the token exists. */
const is_var_fallback = (m: RegExpMatchArray) => /var\(\s*--[\w-]+\s*,\s*$/.test((m.input ?? '').slice(Math.max(0, m.index! - 60), m.index!))

/** Numeric z-index at or above this competes with page chrome and must come from _z-index.scss. */
export const Z_INDEX_LAYER_THRESHOLD = 100

/** Exact version for each CDN's URL scheme. */
const CDN_URL = /https?:\/\/(cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com|ajax\.googleapis\.com)\/[^\s"'`)<>]+/g
const PINNED: Record<string, RegExp> = {
    'cdn.jsdelivr.net': /^https?:\/\/cdn\.jsdelivr\.net\/(?:npm|gh)\/(?:@[^/@]+\/)?[^/@]+@\d+\.\d+\.\d+(?:[/?]|$)/,
    'unpkg.com': /^https?:\/\/unpkg\.com\/(?:@[^/@]+\/)?[^/@]+@\d+\.\d+\.\d+(?:[/?]|$)/,
    'cdnjs.cloudflare.com': /^https?:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/[^/]+\/\d+\.\d+\.\d+\//,
    'ajax.googleapis.com': /^https?:\/\/ajax\.googleapis\.com\/ajax\/libs\/[^/]+\/\d+\.\d+\.\d+\//,
}

export const RULES: ConventionRule[] = [
    {
        id: 'client_fetch',
        kind: 'ratchet',
        why: 'Rule 1: htmx owns server state. Client code (Alpine x-data, <script>) must not call fetch()/axios; render an htmx partial instead.',
        find: (file) => (is_astro(file) ? hits_in(file, [astro_template(file.text)], /\bfetch\s*\(|\baxios\s*[.(]/g) : []),
    },
    {
        id: 'inner_html',
        kind: 'absolute',
        why: 'Rule 1: the client never builds DOM from data. Use an htmx partial instead of innerHTML/outerHTML/insertAdjacentHTML (clearing with = "" is fine).',
        find: (file) =>
            hits_in(file, code_regions(file), /\.(?:inner|outer)HTML\s*\+?=(?!=)(?!\s*(?:''|""|``)\s*[;)\n,}])|\.insertAdjacentHTML\s*\(/g),
    },
    {
        id: 'z_index_layer',
        kind: 'ratchet',
        why: `Rule 3: overlay layers derive from the _z-index.scss chain (var(--dialog-z-index) ...). Numeric z-index >= ${Z_INDEX_LAYER_THRESHOLD} invents a layer; small values for stacking inside a component are fine.`,
        find: (file) => {
            if (file.path === 'src/styles/properties/_z-index.scss') return []
            const css = hits_in(file, css_regions(file), /z-index\s*:\s*(-?\d+)/g, (m) => Math.abs(Number(m[1])) >= Z_INDEX_LAYER_THRESHOLD)
            const tailwind = is_astro(file)
                ? hits_in(file, [astro_template(file.text)], /(?<![\w-])z-\[(-?\d+)\]/g, (m) => Math.abs(Number(m[1])) >= Z_INDEX_LAYER_THRESHOLD)
                : []
            return [...css, ...tailwind]
        },
    },
    {
        id: 'hex_colour',
        kind: 'ratchet',
        why: 'Rule 3: colours come from the tokens in src/styles/properties (var(--fleet-red), var(--highlight), ...), not hex literals.',
        find: (file) => {
            if (file.path.startsWith('src/styles/properties/')) return []
            const hits = hits_in(file, css_regions(file), HEX_IN_DECLARATION, (m) => value_has_hex(m[2]))
            const tailwind = is_astro(file) ? hits_in(file, [astro_template(file.text)], /(?<![\w-])[a-z]+(?:-[a-z]+)*-\[#[0-9a-fA-F]{3,8}\]/g) : []
            return [...hits, ...tailwind]
        },
    },
    {
        id: 'alpha_literal',
        kind: 'ratchet',
        why: 'Rule 3: white/black alpha tints use the tokens in src/styles/properties/_colors.scss (var(--hairline), var(--hairline-strong), var(--text-muted), var(--surface-sunken), ...) or color-mix(in srgb, var(--highlight) N%, transparent), not rgba() literals.',
        find: (file) => {
            if (file.path.startsWith('src/styles/properties/')) return []
            return hits_in(file, css_regions(file), ALPHA_LITERAL, (m) => !is_var_fallback(m))
        },
    },
    {
        id: 'tailwind_apply',
        kind: 'absolute',
        why: 'Rule 3/5: Tailwind is for utilities in markup; no @apply blobs in component styles.',
        find: (file) => hits_in(file, css_regions(file), /@apply\b/g),
    },
    {
        id: 'is_superuser_read',
        kind: 'ratchet',
        why: "Rule 5: access goes through can(await get_gates(Astro), '<gate>') from @helpers/gates; never read the JWT is_superuser claim (gates.ts is the one place that maps it).",
        find: (file) => {
            if (file.path === 'src/helpers/gates.ts') return []
            if (!is_astro(file) && !is_script(file)) return []
            return hits_in(file, [{ text: file.text, offset: 0 }], /\.is_superuser\b|\[\s*['"]is_superuser['"]\s*\]/g)
        },
    },
    {
        id: 't_as_any',
        kind: 'absolute',
        why: "Rule 5: dynamic i18n keys use t_key()/dynamic_key() from @helpers/i18n, not t(x as any), so a typo in a key family fails astro check.",
        find: (file) => hits_in(file, [{ text: file.text, offset: 0 }], /(?<![\w.$])t\((?:[^()]|\([^()]*\))*?\bas\s+any\s*\)/g),
    },
    {
        id: 'cdn_unpinned',
        kind: 'absolute',
        why: 'External scripts and styles name an exact version (pkg@1.2.3), so an upstream release cannot reach production without a deploy.',
        find: (file) =>
            hits_in(file, [{ text: file.text, offset: 0 }], CDN_URL, (m) => {
                const host = m[1]
                return !PINNED[host].test(m[0])
            }),
    },
]

export function rule(id: string): ConventionRule {
    const found = RULES.find((r) => r.id === id)
    if (!found) throw new Error(`unknown rule ${id}`)
    return found
}
