// Reads the design tokens straight from the site's stylesheets, so the
// Foundations pages (and rust/tokens.json) can never fall behind them.
//
// Tiers, following the Design Tokens Community Group format (2025.10):
//   primitive  a raw value:              --fleet-red: #b53620
//   semantic   an alias with a purpose:  --foreground: var(--fleet-yellow)
// Component tokens stay scoped inside each component (define:vars).

// Server-side only (Astro frontmatter, vitest, scripts): stories never import
// this file. Read from disk because vitest stubs `?raw` stylesheets.
// Namespace imports and lazy reads: Storybook's preview bundle follows the
// imports of the .astro files that use this module, so it must load (and do
// nothing) in a browser.
import * as fs from 'node:fs'
import * as path from 'node:path'

const app_root = () => process.env.RUST_APP_ROOT ?? process.cwd()

function read_sources(): Record<string, string> {
    const STYLES_DIR = path.join(app_root(), 'src/styles')
    const { readFileSync, readdirSync } = fs
    const join = path.join
    const files = [
        ...readdirSync(join(STYLES_DIR, 'properties')).filter((f) => f.endsWith('.scss')).map((f) => `properties/${f}`),
        ...readdirSync(join(STYLES_DIR, 'utopia')).filter((f) => f.endsWith('.scss')).map((f) => `utopia/${f}`),
        '_global.scss',
    ]
    return Object.fromEntries(files.map((file) => [`/src/styles/${file}`, readFileSync(join(STYLES_DIR, file), 'utf8')]))
}

let cached_sources: Record<string, string> | null = null
const get_sources = () => (cached_sources ??= read_sources())

export interface Token {
    name:       string;         // --fleet-red
    value:      string;         // #b53620
    file:       string;         // properties/_colors.scss
    group:      string;         // the // comment heading it sits under, or the file
    tier:       'primitive' | 'semantic';
    references: string[];       // tokens it aliases
    kind:       TokenKind;
}

export type TokenKind = 'color' | 'space' | 'font-size' | 'font-family' | 'z-index' | 'transition' | 'size' | 'other'

export interface ThemeOverride {
    selector:   string;         // body.color-blind-mode
    tokens:     { name: string; value: string }[];
}

const COLOR_VALUE = /^(#[0-9a-f]{3,8}|rgba?\(|hsla?\(|color-mix\(|white$|black$|transparent$)/i

function kind_of(name: string, value: string, file: string): TokenKind {
    if (file.includes('_colors') || COLOR_VALUE.test(value)) return 'color'
    if (file.includes('utopia/_space') || name.startsWith('--space-')) return 'space'
    if (file.includes('utopia/_type') || file.includes('_font-sizes') || name.startsWith('--step-')) return 'font-size'
    if (file.includes('_font-families') || name.endsWith('-font')) return 'font-family'
    if (file.includes('_z-index')) return 'z-index'
    if (file.includes('_transitions')) return 'transition'
    if (file.includes('_layout')) return 'size'
    return 'other'
}

function short_file(path: string) {
    return path.replace(/^.*\/src\/styles\//, '')
}

// Declarations directly inside one selector block (no nesting in these files).
function blocks(source: string) {
    const found: { selector: string; body: string; start: number }[] = []
    const re = /([^{}]+)\{([^{}]*)\}/g
    for (let match = re.exec(source); match; match = re.exec(source))
        found.push({ selector: match[1].trim().split('\n').pop()!.trim(), body: match[2], start: match.index })
    return found
}

function declarations(body: string) {
    const out: { name: string; value: string; group: string | null }[] = []
    let group: string | null = null
    for (const raw of body.split('\n')) {
        const line = raw.trim()
        const comment = /^(?:\/\/|\/\*)\s*(.+?)\s*(?:\*\/)?$/.exec(line)
        if (comment && !line.includes(':')) {
            group = comment[1]
            continue
        }
        if (line === '')
            continue
        const decl = /^(--[\w-]+)\s*:\s*(.+?);?\s*(?:\/\/.*)?$/.exec(line)
        if (decl)
            out.push({ name: decl[1], value: decl[2].replace(/;$/, '').trim(), group })
    }
    return out
}

export function read_tokens(): Token[] {
    const tokens: Token[] = []
    for (const [path, source] of Object.entries(get_sources())) {
        const file = short_file(path)
        for (const block of blocks(source)) {
            if (block.selector !== ':root')
                continue
            for (const { name, value, group } of declarations(block.body)) {
                const references = [...value.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1])
                tokens.push({
                    name,
                    value,
                    file,
                    group: group ?? file,
                    tier: references.length ? 'semantic' : 'primitive',
                    references,
                    kind: kind_of(name, value, file),
                })
            }
        }
    }
    return tokens
}

// Theme modes: body classes that redefine root tokens (body.color-blind-mode).
export function read_theme_overrides(): ThemeOverride[] {
    const overrides: ThemeOverride[] = []
    for (const source of Object.values(get_sources())) {
        for (const block of blocks(source)) {
            if (!block.selector.startsWith('body.'))
                continue
            const tokens = declarations(block.body).map(({ name, value }) => ({ name, value }))
            if (tokens.length)
                overrides.push({ selector: block.selector, tokens })
        }
    }
    return overrides
}

// UI scaling classes the accessibility options put on <body>.
export function read_ui_scales(): number[] {
    const scales = new Set<number>([100])
    for (const source of Object.values(get_sources()))
        for (const match of source.matchAll(/\.ui-scaling-(\d+)\s*\{/g))
            scales.add(Number(match[1]))
    return [...scales].sort((a, b) => a - b)
}

export function tokens_of(kind: TokenKind) {
    return read_tokens().filter((token) => token.kind === kind)
}

export function group_by<T>(items: T[], key: (item: T) => string) {
    const groups = new Map<string, T[]>()
    for (const item of items) {
        const k = key(item)
        groups.set(k, [...(groups.get(k) ?? []), item])
    }
    return groups
}

// The Design Tokens Community Group (2025.10) JSON for every root token:
// { "color": { "fleet-red": { "$type": "color", "$value": "#b53620" } } }
// Aliases become references ("{color.fleet-yellow}"), so tools can follow the tiers.
export function to_dtcg(tokens = read_tokens()) {
    const DTCG_TYPE: Record<TokenKind, string | undefined> = {
        'color': 'color', 'space': 'dimension', 'font-size': 'dimension', 'font-family': 'fontFamily',
        'z-index': 'number', 'transition': 'transition', 'size': 'dimension', 'other': undefined,
    }
    const path_of = new Map(tokens.map((token) => [token.name, `${token.kind}.${token.name.slice(2)}`]))
    const tree: Record<string, Record<string, Record<string, unknown>>> = {}
    for (const token of tokens) {
        const alias = token.references.length === 1 && token.value === `var(${token.references[0]})`
            ? path_of.get(token.references[0]) : undefined
        tree[token.kind] ??= {}
        tree[token.kind][token.name.slice(2)] = {
            ...(DTCG_TYPE[token.kind] ? { $type: DTCG_TYPE[token.kind] } : {}),
            $value: alias ? `{${alias}}` : token.value,
            $description: token.group !== token.file ? token.group : undefined,
            $extensions: { 'org.minmatar.rust': { css: token.name, file: `src/styles/${token.file}`, tier: token.tier } },
        }
    }
    return tree
}

// Colour families for the Colors page, by what the token is for.
export function color_family(token: Token): string {
    const name = token.name.slice(2)
    if (name.startsWith('security-status')) return 'Security status'
    if (/^(tech-|storyline|faction|officer|deadspace|abyssal)/.test(name)) return 'Item meta groups'
    if (name.startsWith('discord-')) return 'Discord'
    if (name.endsWith('-blind')) return 'Colour-blind mode'
    if (/transparency|backdrop/.test(name)) return 'Glass (effects)'
    if (/^(hairline|text-muted|glow|surface-sunken|border-color|faded)/.test(name)) return 'Alpha tints'
    if (token.tier === 'semantic' || /^(foreground|background|component-background|highlight|form-color|button-color|skeleton)/.test(name)) return 'Semantic'
    return 'Brand palette'
}

export const COLOR_FAMILIES = ['Brand palette', 'Semantic', 'Alpha tints', 'Colour-blind mode', 'Glass (effects)', 'Item meta groups', 'Security status', 'Discord']

// ---- Whole-app scan: fonts and colours used outside the token files ----

let source_files: { path: string; text: string }[] | null = null

function walk(dir: string, out: string[]) {
    for (const entry of fs.readdirSync(dir)) {
        const full = path.join(dir, entry)
        if (fs.statSync(full).isDirectory()) {
            if (entry !== 'data' && entry !== 'generated')
                walk(full, out)
        } else if (/\.(astro|scss|css)$/.test(entry)) {
            out.push(full)
        }
    }
    return out
}

export function app_sources() {
    const src_dir = path.join(app_root(), 'src')
    source_files ??= walk(src_dir, []).map((file) => ({ path: file.slice(src_dir.length + 1), text: fs.readFileSync(file, 'utf8') }))
    return source_files
}

export interface FontFamily {
    family:     string;
    source:     'self-hosted' | 'fontsource' | 'google-fonts' | 'system';
    tokens:     string[];       // --heading-font, --chronicle-font, ...
    files:      string[];       // where a token or @import declares it
}

const SYSTEM_FAMILIES = new Set(['sans-serif', 'serif', 'monospace', 'ui-monospace', 'system-ui', 'inherit', 'Georgia', 'Times New Roman', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas'])

// Every font family the app declares: root font tokens, component-scoped
// `--*-font` tokens, @font-face, @fontsource imports and Google Fonts @imports.
export function read_font_families(): FontFamily[] {
    const families = new Map<string, FontFamily>()
    const add = (family: string, source: FontFamily['source'], token?: string, file?: string) => {
        family = family.trim().replace(/^['"]|['"]$/g, '')
        if (!family || family.startsWith('var(') || family === 'inherit')
            return
        const entry = families.get(family) ?? { family, source: SYSTEM_FAMILIES.has(family) ? 'system' : source, tokens: [], files: [] }
        if (token && !entry.tokens.includes(token)) entry.tokens.push(token)
        if (file && !entry.files.includes(file)) entry.files.push(file)
        families.set(family, entry)
    }

    const font_face_families = new Set<string>()
    for (const source of Object.values(get_sources()))
        for (const m of source.matchAll(/font-family:\s*'([^']+)'/g)) font_face_families.add(m[1])
    for (const { text } of app_sources())
        for (const m of text.matchAll(/@font-face\s*\{[^}]*font-family:\s*['"]([^'"]+)['"]/g)) font_face_families.add(m[1])

    const google = new Set<string>()
    for (const { text } of app_sources())
        for (const m of text.matchAll(/fonts\.googleapis\.com\/css2\?([^'")]+)/g))
            for (const f of m[1].matchAll(/family=([^:&]+)/g)) google.add(decodeURIComponent(f[1].replace(/\+/g, ' ')))

    const source_of = (family: string): FontFamily['source'] => {
        if (font_face_families.has(family)) return 'self-hosted'
        if (google.has(family)) return 'google-fonts'
        if (/Montserrat|Qahiri/.test(family)) return 'fontsource'
        return 'system'
    }

    // Root tokens resolve through other tokens (--heading-font: var(--minmatar)).
    const root = new Map(read_tokens().filter((t) => t.kind === 'font-family').map((t) => [t.name, t.value]))
    const resolve = (value: string, depth = 0): string => depth > 5 ? value :
        value.replace(/var\((--[\w-]+)\)/g, (_, name) => root.has(name) ? resolve(root.get(name)!, depth + 1) : '')
    for (const [name, value] of root)
        for (const family of resolve(value).split(','))
            add(family, source_of(family.trim().replace(/['"]/g, '')), name, 'styles/properties/_font-families.scss')

    for (const { path, text } of app_sources()) {
        for (const m of text.matchAll(/(--[\w-]+-font)\s*:\s*([^;]+);/g)) {
            if (path.startsWith('styles/properties/')) continue
            for (const family of m[2].split(','))
                add(family, source_of(family.trim().replace(/['"]/g, '')), m[1], path)
        }
        for (const m of text.matchAll(/font-family:\s*([^;]+);/g)) {
            if (m[1].includes('var(')) continue
            for (const family of m[1].split(','))
                add(family, source_of(family.trim().replace(/['"]/g, '')), undefined, path)
        }
    }
    for (const family of google) add(family, 'google-fonts')
    for (const family of font_face_families) add(family, 'self-hosted')

    return [...families.values()].filter((f) => f.family !== 'swiper-icons')
}

export interface OffTokenColor {
    value:  string;     // #c0392b
    count:  number;
    files:  string[];
}

// Hex colours written into components and pages instead of a token.
export function read_off_token_colors(): OffTokenColor[] {
    const colors = new Map<string, OffTokenColor>()
    for (const { path, text } of app_sources()) {
        if (path.startsWith('styles/properties/') || path.startsWith('styles/utopia/'))
            continue
        const css = [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n') || (path.endsWith('.astro') ? '' : text)
        for (const m of css.matchAll(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b(?![\w-])/g)) {
            const value = `#${m[1].toLowerCase()}`
            const entry = colors.get(value) ?? { value, count: 0, files: [] }
            entry.count += 1
            if (!entry.files.includes(path)) entry.files.push(path)
            colors.set(value, entry)
        }
    }
    return [...colors.values()].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
}
