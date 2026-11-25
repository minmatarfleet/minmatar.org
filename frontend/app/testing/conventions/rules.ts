// The machine-checked subset of .claude/rules/frontend-design.md.
//
// `ratchet` rules have existing offenders: baseline.json holds the allowed
// count per file, and a file may only go down. `absolute` rules have no
// offenders left, so any hit fails. When a ratchet rule's baseline reaches
// zero, move it to `absolute` and drop its key from baseline.json.
//
// Keep every rule narrow enough that a hit is always a real violation.

import { astro_template, css_regions, hits_in, line_at, type Hit, type Region, type SourceFile } from './scan'

export interface ConventionRule {
    id: string
    kind: 'ratchet' | 'absolute'
    /** What the rule protects and what to do instead; printed on failure. */
    why: string
    find: (file: SourceFile) => Hit[]
    /**
     * File path -> reason. An exempt file is never scanned by this rule. Use it only for code that
     * legitimately cannot use the library (a `pre` block, a heatmap matrix, game data drawn in game
     * colours); the reasons are printed in the test output. Keep each reason specific.
     */
    exempt?: Record<string, string>
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

/** `color-mix(in srgb, <colour> 45%, transparent)`: a literal percentage over transparent. */
const TINT_LITERAL = /color-mix\(\s*in srgb\s*,(?:[^()]|\([^()]*\))*?\s[\d.]+%\s*,\s*transparent\s*\)/g
/** The retired colour tokens as custom properties; `--attention` inside a class name (`meta--attention`) is not one. */
const RETIRED_TOKEN = /(?<![\w-])--(?:attention|text-muted|hairline(?:-medium|-strong)?|glow)(?![\w-])/g

// `none` and the translate(-50%) centring idiom position an element; they are not a hover effect.
const MOTION_DECLARATION = /^(?:transform|scale|translate|rotate)\s*:(?!\s*(?:none\b|translate[XY]?\(\s*-50%[^)]*\)\s*(?:!important\s*)?$))/
const HOVER_GATE = /@media[^{]*\(\s*hover\s*:\s*hover\s*\)/

/**
 * `transform`/`scale`/`translate`/`rotate` declarations that apply on :hover
 * without an enclosing `@media (hover: hover)`. Walks the nested (SCSS) block
 * structure, so `&:hover` inside a rule and gating on any ancestor both count.
 */
function ungated_hover_motion(file: SourceFile, region: Region): Hit[] {
    // Blank out comments, keeping offsets (// only at line start or after whitespace, so url(https://...) survives).
    const text = region.text.replace(/\/\*[\s\S]*?\*\/|(^|[\s;{}])\/\/[^\n]*/g, (m) => m.replace(/[^\n]/g, ' '))
    const hits: Hit[] = []
    const stack: string[] = []
    let start = 0
    for (let i = 0; i < text.length; i++) {
        const c = text[i]
        if (c !== '{' && c !== '}' && c !== ';') continue
        const chunk = text.slice(start, i).trim()
        if (c === '{') stack.push(chunk)
        else {
            const hovered = stack.some((s) => /:hover\b/.test(s) && !s.startsWith('@'))
            const gated = stack.some((s) => HOVER_GATE.test(s))
            if (hovered && !gated && MOTION_DECLARATION.test(chunk)) {
                const index = region.offset + start + (text.slice(start, i).length - text.slice(start, i).trimStart().length)
                hits.push({ line: line_at(file.text, index), snippet: `${stack.filter((s) => !s.startsWith('@')).at(-1)} { ${chunk} }`.replace(/\s+/g, ' ').slice(0, 80) })
            }
            if (c === '}') stack.pop()
        }
        start = i + 1
    }
    return hits
}

/** A class selector for a hand-styled empty state: `.activity-empty`, `.cm-empty`, `.x__empty-title`. Not `--empty` modifiers or `.is-empty` states. */
const BESPOKE_EMPTY_SELECTOR = /\.(?!is-empty\b)[a-z][\w-]*?(?:__empty|[a-z0-9]-empty)(?:-[a-z]+)?(?![\w-])(?=[^{};]*\{)/g

/** Partials that read the API render failures with ErrorRefetch, or say why not (`no-error-refetch: <reason>`, e.g. a form result). */
const DATA_HELPER_IMPORT = /from\s+['"]@helpers\/(?:api\.minmatar\.org|fetching)\//

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

/** Blank CSS comments in place (same length), so a commented-out declaration is not a hit. `https://` is kept. */
const without_css_comments = (region: Region): Region => ({
    text: region.text.replace(/\/\*[\s\S]*?\*\/|(?<![:\w(])\/\/[^\n]*/g, (m) => m.replace(/[^\n]/g, ' ')),
    offset: region.offset,
})

/** Element start tag for `<table`/`<button`/`<select`, not `<tablet-x` or `<button-group`. */
const RAW_TABLE = /<table(?=[\s>/])|\srole=["']table["']/g
const RAW_STYLED_BUTTON = /<button(?=[\s>/])/g
/** `<select`, `<textarea`, and `<input` unless its static type is hidden, submit or button. */
const RAW_FORM_CONTROL = /<(?:select|textarea)(?=[\s>/])|<input(?=[\s/>])(?![^>]*?(?<![\w-])type\s*=\s*["']?(?:hidden|submit|button)(?=["'\s/>]))[^>]*>/g
/** The element's own role, not `[role="tablist"]` in a selector. */
const ROLE_TABLIST = /\srole=["']tablist["']/g
const CLICK_OUTSIDE = /(?:x-on:|@)click\.outside(?![\w-])/g
const DIRECT_TIPPY = /(?<![\w.$])tippy\s*\(/g
const OVERFLOW_X_SCROLL_CSS = /(?<![\w-])overflow-x\s*:\s*(?:auto|scroll)(?![\w-])/g
/**
 * `<pre>` blocks come out of markdown (set:html), so they cannot be wrapped in XFadeScroll: a
 * declaration inside a rule whose selector names `pre` is exempt. Walks back to the rule's `{`.
 */
const in_pre_rule = (text: string, index: number): boolean => {
    let depth = 0
    let open = -1
    for (let i = index - 1; i >= 0; i--) {
        if (text[i] === '}') depth++
        else if (text[i] === '{') {
            if (depth === 0) { open = i; break }
            depth--
        }
    }
    if (open < 0) return false
    let start = open
    while (start > 0 && !'{};'.includes(text[start - 1])) start--
    return /(?<![\w-])pre(?![\w-])/.test(text.slice(start, open))
}
const OVERFLOW_X_SCROLL_CLASS = /(?<![\w-])overflow-x-(?:auto|scroll)(?![\w-])/g
/** An hx-get attribute value: quoted, or an Astro expression. Captures the value in groups 1-3. */
const HX_GET_VALUE = /<[a-zA-Z][^>]*?\shx-get=(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g
const PAGE_PARAM = /[?&]page(?:_num)?=/
/** A class token ending in chip, pill or chips: `fleet-type-chip`, `chip`. Not `spill`, `chip-list` or `chip__label`. */
const CHIP_TOKEN = /(?<![a-z0-9-])(?:[a-z0-9]+-)*(?:chips?|pills?)(?![\w-])/
const GOOGLE_FONTS = /fonts\.googleapis\.com/g
/** A font-family declaration that is not a `var(--token)` or `inherit`; `$font-family` SCSS variables are skipped. */
const FONT_FAMILY_LITERAL = /(?<![\w$-])font-family\s*:(?!\s*(?:var\(|inherit\b))\s*[^;{}\s][^;{}\n]*/g
/** Meta-group and security-status tokens carry a fixed meaning; only the components that draw them may use them. */
const OFF_MEANING_TOKEN = /var\(\s*--(?:security-status-[\w-]+|tech-i{1,3}|storyline|faction|officer|deadspace|abyssal)(?![\w-])/g
const TEXT_STATUS_BLOCK = /\.text-status-[\w-]+[^{]*\{[^}]*\}/g
/** A custom-property definition named for a semantic meaning (`--hp-warn:`), not a token that holds a colour (`--fleet-red:`). */
const LOCAL_SEMANTIC_DEFINITION = /(?<![\w-])--[\w-]*[_-](?:warn|good|bad|warning|success|danger)\s*:/g

const EVE_IMAGE_HELPERS = ['src/helpers/eve_image.ts', 'src/helpers/landing.ts', 'src/helpers/fleet_rsvp.ts']
const EVE_IMAGE_COMPONENTS = ['Picture', 'CharacterPicture', 'CorporationPicture', 'ItemPicture'].map((n) => `src/components/blocks/${n}.astro`)
const COMPONENT_FILES = (...names: string[]) => names.map((n) => `src/components/${n}.astro`)

const RULE_DEFINITIONS: ConventionRule[] = [
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
        why: 'Rule 3: white/black alpha tints use the tokens in src/styles/properties/_colors.scss (var(--border-color), var(--border-color-hover), var(--faded), var(--surface-sunken), ...) or color-mix(in srgb, var(--highlight) N%, transparent), not rgba() literals.',
        find: (file) => {
            if (file.path.startsWith('src/styles/properties/')) return []
            return hits_in(file, css_regions(file), ALPHA_LITERAL, (m) => !is_var_fallback(m))
        },
    },
    {
        id: 'tint_off_ladder',
        kind: 'absolute',
        why: 'Rule 3: a colour over transparent uses the tint ladder: color-mix(in srgb, var(--fleet-yellow) var(--tint-soft), transparent) with --tint-subtle (8%), --tint-soft (15%), --tint-medium (30%), --tint-strong (45%), --tint-bold (60%), --tint-heavy (75%) or --tint-dense (90%), not a literal percentage.',
        find: (file) => hits_in(file, [{ text: file.text, offset: 0 }], TINT_LITERAL),
    },
    {
        id: 'retired_token',
        kind: 'absolute',
        why: 'Rule 3: --attention, --text-muted, --hairline, --hairline-medium, --hairline-strong and --glow are retired. Use --fleet-yellow, --faded, --border-color and --border-color-hover (see docs/frontend-design.md).',
        find: (file) => hits_in(file, [{ text: file.text, offset: 0 }], RETIRED_TOKEN),
    },
    {
        id: 'skeleton_keyframes',
        kind: 'absolute',
        why: 'Loading skeletons use @include skeleton.shimmer / skeleton.pulse from src/styles/mixins/_skeleton.scss: one set of keyframes (styles/_animations.scss) that stops under prefers-reduced-motion. Do not define per-component skeleton keyframes.',
        find: (file) => {
            if (file.path === 'src/styles/_animations.scss') return []
            return hits_in(file, css_regions(file), /@keyframes\s+[\w-]*(?:skel|shimmer)[\w-]*/g)
        },
    },
    {
        id: 'hover_motion_ungated',
        kind: 'absolute',
        why: 'Rule 6: hover transforms (scale/translate/rotate) go inside @media (hover: hover), or touch screens keep the element stuck mid-effect after a tap. Keep a :focus-visible variant outside the query; touch press states go in @media (hover: none) on :active.',
        find: (file) => css_regions(file).flatMap((region) => ungated_hover_motion(file, region)),
    },
    {
        id: 'bespoke_empty_state',
        kind: 'ratchet',
        why: 'Empty lists and panels render <EmptyState title={t(...)} /> (or title + hint), styled once in src/styles/components/_empty-state.scss so it also works inside htmx partials. Do not style a new __empty / -empty class.',
        find: (file) => {
            if (file.path.startsWith('src/styles/')) return []
            return hits_in(file, css_regions(file), BESPOKE_EMPTY_SELECTOR)
        },
    },
    {
        id: 'partial_error_state',
        kind: 'ratchet',
        why: 'A partial that fetches from the API renders its failure with <ErrorRefetch args={{ partial, error, delay }} /> (retry with backoff). Mutation partials that show inline form errors instead add a `no-error-refetch: <reason>` comment.',
        find: (file) => {
            if (!file.path.startsWith('src/pages/partials/') || !is_astro(file)) return []
            if (!DATA_HELPER_IMPORT.test(file.text) || /ErrorRefetch|no-error-refetch:/.test(file.text)) return []
            return [{ line: 1, snippet: 'fetches API data without ErrorRefetch' }]
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
        id: 'hand_rolled_action_menu',
        kind: 'absolute',
        why: 'Action dropdowns are <ActionMenu> with <ActionMenuItem> children (links, submits, two-step confirms, text_only status lines); a component with its own trigger goes in <div class="action-menu-item-host">. Do not fill a raw <Dropdown> with an actions list or hand-roll an actions popup.',
        find: (file) => {
            if (!is_astro(file) || file.path === 'src/components/blocks/ActionMenu.astro') return []
            const template = [astro_template(file.text)]
            const dropdowns = hits_in(file, template, /<Dropdown\b[\s\S]*?<\/Dropdown>/g, (m) => /\bt\(\s*['"]actions['"]\s*\)/.test(m[0]))
            const popups = hits_in(file, template, /<[a-zA-Z]+\b(?=[^>]*aria-haspopup="(?:true|menu)")(?=[^>]*aria-label="[^"]*\bactions\b[^"]*")[^>]*>/gi)
            return [...dropdowns, ...popups]
        },
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
    {
        id: 'cdn_script_processed',
        kind: 'absolute',
        why:
            'A <script src="https://..."> with no other attribute is processed by Astro, which turns it into a module or drops it, so a global it defines (window.mediumZoom) is never there when Alpine runs x-init (MINMATAR-FRONTEND-HY). Add is:inline (or defer) so it stays a classic script.',
        find: (file) => (is_astro(file) ? hits_in(file, [{ text: file.text, offset: 0 }], /<script\s+src\s*=\s*["']https?:\/\/[^"']*["']\s*>/g) : []),
    },
    {
        id: 'alpine_factory_in_body',
        kind: 'absolute',
        why:
            'An x-data factory (window.name = ...) defined in an is:inline script of a page or block does not exist yet on a ClientRouter soft navigation: Alpine inits the swapped-in x-data before the page\'s inline scripts run, so every expression in it fails and the markup renders empty (MINMATAR-FRONTEND-KS). Define it in a <head> partial loaded before AlpineCdn (LandingAlpine, LearningAlpine) instead.',
        find: (file) => {
            if (!is_astro(file) || file.path.startsWith('src/components/partials/')) return []
            const template = astro_template(file.text)
            const hits: Hit[] = []
            for (const script of file.text.matchAll(/<script\s+is:inline\s*>([\s\S]*?)<\/script>/g)) {
                const body_offset = script.index! + script[0].indexOf(script[1])
                for (const m of script[1].matchAll(/(?<![\w.])window\.(\w+)\s*=(?!=)/g)) {
                    // Only a factory some x-data on this file calls: `x-data="name(...)"` or `...name(...)`.
                    const used = new RegExp(`x-data=[\\s\\S]{0,200}?(?<![\\w.])${m[1]}\\s*\\(`).test(template.text)
                    if (!used) continue
                    const index = body_offset + m.index!
                    hits.push({ line: line_at(file.text, index), snippet: m[0] })
                }
            }
            return hits
        },
    },
    {
        id: 'raw_eve_image',
        kind: 'ratchet',
        why: 'EVE image URLs come from @helpers/eve_image (get_item_icon, get_player_icon, get_corporation_logo, ...) or the Picture components (<ItemPicture>, <CharacterPicture>, <CorporationPicture>, <Picture>), which pick the size and the fallback. Do not write an images.evetech.net URL in markup or scripts.',
        find: (file) => {
            if (EVE_IMAGE_HELPERS.includes(file.path) || EVE_IMAGE_COMPONENTS.includes(file.path)) return []
            return hits_in(file, [{ text: file.text, offset: 0 }], /(?:https?:)?\/\/images\.evetech\.net/g)
        },
    },
    {
        id: 'raw_table',
        kind: 'absolute',
        why: 'Tables are <DataGrid> (sortable, responsive) or <RowList> (the styled base); a hand-written <table> or role="table" skips both. Use the library table.',
        exempt: {
            'src/components/blocks/ship-guide/GuideMatchupChart.astro': 'heatmap matrix: ship-by-ship cells coloured by value, rows and columns are the data',
            'src/components/blocks/structures/StructureRigChip.astro': 'tooltip table: a small key/value table inside a Tippy popover, styled by global popover rules',
            'src/pages/list_data.astro': 'in-flight landing work (owner: keep untouched)',
            'src/pages/partials/corporation_members_table_component.astro': 'bulk-select header is swapped by Alpine and column headers sort by htmx (hx-get on th); DataGrid owns neither',
        },
        find: (file) => {
            if (!is_astro(file) || COMPONENT_FILES('blocks/DataGrid', 'blocks/DataTable', 'blocks/RowList', 'blocks/campaigns/etherium-reach/CampaignDataTable', 'blocks/manage/ManageTable', 'blocks/manage/RowSwapFrame').includes(file.path)) return []
            return hits_in(file, [astro_template(file.text)], RAW_TABLE)
        },
    },
    {
        id: 'overflow_x_scroll',
        kind: 'ratchet',
        why: 'Wide tables and chip rows scroll inside <XFadeScroll> (it adds the edge fades and the scroll affordance), not a hand-rolled overflow-x: auto/scroll. Rules for `pre` are exempt: markdown code blocks are set:html and cannot be wrapped.',
        find: (file) => {
            if (file.path === 'src/components/compositions/XFadeScroll.astro') return []
            const css = hits_in(file, css_regions(file).map(without_css_comments), OVERFLOW_X_SCROLL_CSS, (m) => !in_pre_rule(m.input!, m.index!))
            const tailwind = is_astro(file) ? hits_in(file, [astro_template(file.text)], OVERFLOW_X_SCROLL_CLASS) : []
            return [...css, ...tailwind]
        },
    },
    {
        id: 'direct_tippy',
        kind: 'ratchet',
        why: 'Tooltips are <Tippy> (or the tippy_options on a swapped partial, initialised by swap_init.ts). A direct tippy(...) call is not re-initialised after an htmx swap.',
        find: (file) => {
            const exempt = ['src/helpers/swap_init.ts', 'src/components/blocks/Tippy.astro', 'src/components/partials/TippyBootstrap.astro']
            if (exempt.includes(file.path)) return []
            return hits_in(file, code_regions(file), DIRECT_TIPPY)
        },
    },
    {
        id: 'hand_rolled_tablist',
        kind: 'absolute',
        why: 'Tab strips are <SectionTabs> (keyboard, aria and the hash-linked active tab), not a hand-written role="tablist".',
        exempt: {
            'src/components/blocks/role-guide/RoleAmmoChart.astro': 'icon-image tabs placed below their chart with arrow-key roving; SectionTabs is a text strip above hash-linked panels',
            'src/components/blocks/role-guide/RoleModulePanel.astro': 'icon-image tabs placed below their panel with arrow-key roving; SectionTabs is a text strip above hash-linked panels',
        },
        find: (file) => {
            if (!is_astro(file) || file.path === 'src/components/blocks/SectionTabs.astro') return []
            return hits_in(file, [astro_template(file.text)], ROLE_TABLIST)
        },
    },
    {
        id: 'hand_rolled_popover',
        kind: 'absolute',
        why: 'Click-away popups are <Dropdown>, <ActionMenu>, <Dialog>/<DialogButton> or <Modal> (focus, Escape and stacking handled); a bare @click.outside re-implements them.',
        exempt: {
            'src/components/blocks/ActionMenuItem.astro': 'two-step confirm inside an action menu: cancels the confirm state on click-away, it is not a popover',
            'src/components/blocks/FleetInvites.astro': 'closes the typeahead result list of a search input; not a click-away popup',
            'src/components/blocks/Neocom.astro': 'mobile navigation drawer: slides in from the edge and closes on click-away, not an anchored popover',
            'src/components/page/partials/PageHeader.astro': 'collapsible subheader action bar on small screens (in-flow, not a floating popup)',
            'src/pages/partials/fleet_pick_ships_modal_component.astro': 'ship picker listbox inside a modal row with a rich trigger; Dropdown cannot host the trigger',
            'src/pages/ships/doctrines/edit/[doctrine_id].astro': 'closes the typeahead result list of the fitting search; not a click-away popup',
        },
        find: (file) => {
            if (!is_astro(file)) return []
            const exempt = COMPONENT_FILES(
                'blocks/Dropdown', 'blocks/ActionMenu', 'blocks/Dialog', 'blocks/DialogButton', 'blocks/Modal',
                'page/PageBreadcrumbs', 'page/BreadcrumbHub', 'blocks/Combobox',
            )
            if (exempt.includes(file.path)) return []
            return hits_in(file, [astro_template(file.text)], CLICK_OUTSIDE)
        },
    },
    {
        id: 'raw_form_control',
        kind: 'absolute',
        why: 'Form controls are <Input>, <Select>, <Textarea>, <RadioCheckInput>, <Switch>, <FlatPicker> (labels, errors, the token styling); a raw <select>, <textarea> or non-hidden <input> bypasses them.',
        exempt: {
            'src/components/blocks/DiscordServerAccess.astro': 'borderless text input typed inside a chip tray (the tray draws the field border); Input would add a second shell',
            'src/components/blocks/FittingBuyOrderContractPrices.astro': 'number field nested inside a segmented radio chip ("custom %"); Input is a block shell and would break the chip',
            'src/components/blocks/fleet_rsvp/FleetRsvpForm.astro': 'visually hidden checkbox of a whole-row pilot card with a drawn tick; the card, not the input, is the control',
            'src/components/blocks/FleetFightsEdit.astro': 'leading checkbox of a table-like fight row grid (label sits in the row grid, not beside the box)',
            'src/components/blocks/FleetShipTargetOwners.astro': 'leading checkbox of a four-column owner row; the label owns the grid',
            'src/components/blocks/manage/KitGrid.astro': 'amount cell with dirty-state styling (.manage-amount) inside a composite grid; Input shell breaks the cell',
            'src/pages/partials/srp_programs_component.astro': 'amount cell with dirty-state styling (.manage-amount) inside a table row; Input shell breaks the cell',
            'src/components/blocks/manage/ManageSwitch.astro': 'the manage-surface role=switch primitive: it is the library control for these forms',
            'src/components/blocks/SelectFinder.astro': 'hidden <select> that Alpine keeps in sync with the searchable list; never shown',
            'src/components/blocks/structures/StructureSettingsForm.astro': 'native multi-select listbox (size=8); Select draws a single-choice caret shell',
            'src/pages/industry/orders/planner.astro': 'checkbox row inside an Alpine x-for template with a column layout owned by the label',
            'src/pages/partials/campaign_settings_component.astro': 'visually hidden checkbox of a retire/undo text toggle (two labels swap on :checked)',
            'src/pages/partials/corporation_members_table_component.astro': 'row-select and select-all checkboxes of the members table; header is Alpine-swapped and sorted by htmx (see raw_table)',
            'src/pages/partials/order_line_pricing_component.astro': 'connected four-up segmented radio bar with one shared border; OptionCard draws separate cards',
        },
        find: (file) => {
            if (!is_astro(file)) return []
            const exempt = COMPONENT_FILES(
                'blocks/Input', 'blocks/Select', 'blocks/Textarea', 'blocks/RadioCheckInput',
                'blocks/Switch', 'blocks/FlatPicker', 'blocks/FilterChip', 'blocks/OptionCard', 'blocks/RadioCheckPill', 'blocks/RadioCheck',
            )
            if (exempt.includes(file.path)) return []
            return hits_in(file, [astro_template(file.text)], RAW_FORM_CONTROL)
        },
    },
    {
        id: 'raw_styled_button',
        kind: 'absolute',
        why: 'Buttons are <Button> (variants, sizes, loading and focus states), <StylessButton> for a bare control, or <ButtonConfirm>/<ClipboardButton>/<CollapsableButton>; a raw <button> skips the styling.',
        exempt: {
            'src/components/blocks/SectionTabs.astro': 'the tab strip primitive itself: its tabs are the role=tab buttons that SectionTabs exists to render',
        },
        find: (file) => {
            if (!is_astro(file)) return []
            const exempt = COMPONENT_FILES('blocks/Button', 'blocks/StylessButton', 'blocks/ButtonConfirm', 'blocks/ClipboardButton', 'blocks/CollapsableButton')
            if (exempt.includes(file.path)) return []
            return hits_in(file, [astro_template(file.text)], RAW_STYLED_BUTTON)
        },
    },
    {
        id: 'raw_chip',
        kind: 'absolute',
        why: 'Filter and status chips are <FilterChip> or <ChipGroup>, and labels are <Tag>; a hand-styled *-chip / *-pill class re-creates them without their states.',
        exempt: {
            'src/components/blocks/amamake-market/AmamakeMarketVolumeSkeleton.astro': 'skeleton shimmer placeholder: chip-shaped blocks that stand in for content, not chips',
            'src/components/blocks/FleetScheduleSkeleton.astro': 'skeleton shimmer placeholder: chip-shaped blocks that stand in for content, not chips',
            'src/components/blocks/universe/UniverseSkeleton.astro': 'skeleton shimmer placeholder: chip-shaped blocks that stand in for content, not chips',
            'src/components/blocks/capital-guide/CapitalGuideShipChip.astro': 'a hull tile (ship render above its name, linking to a fitting), not a filter or status chip',
            'src/components/blocks/structures/StructureRigChip.astro': 'a rig tile: use icon, tier steps and a tooltip anchor, not a filter or status chip',
            'src/components/blocks/TribeGroupChip.astro': 'a crest + group name link (Tag takes text only); a tribe identity badge, not a filter or status chip',
            'src/components/blocks/FleetBattleReport.astro': 'saved-segment scope chip: a link plus its own delete form (hx-post with hidden fields), which FilterChip removable cannot express',
            'src/components/blocks/FleetParticipantsPilots.astro': 'pilot roster entry (portrait, name, kill and loss badges), not a filter or status chip',
        },
        find: (file) => {
            if (!is_astro(file)) return []
            const exempt = COMPONENT_FILES('blocks/FilterChip', 'blocks/ChipGroup', 'blocks/Tag')
            if (exempt.includes(file.path)) return []
            // Quoted class values, or the string literals inside class:list={[...]} (a bare identifier is JS, not a class).
            const has_chip = (m: RegExpMatchArray) => {
                const value = m[1] ?? m[2] ?? [...(m[3] ?? '').matchAll(/(["'`])([^"'`]*)\1/g)].map((s) => s[2]).join(' ')
                return CHIP_TOKEN.test(value)
            }
            return hits_in(file, [astro_template(file.text)], /\sclass(?::list)?=(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g, has_chip)
        },
    },
    {
        id: 'hand_rolled_pager',
        kind: 'ratchet',
        why: 'Paged htmx lists are <HtmxPager> (page state, the swap target and the disabled ends), not an hx-get that builds its own ?page= link.',
        find: (file) => {
            if (!is_astro(file) || file.path === 'src/components/blocks/HtmxPager.astro') return []
            return hits_in(file, [astro_template(file.text)], HX_GET_VALUE, (m) => PAGE_PARAM.test(m[1] ?? m[2] ?? m[3] ?? ''))
        },
    },
    {
        id: 'component_font',
        kind: 'absolute',
        why: 'Fonts load once from src/styles/_fonts.scss and are used through the font tokens (var(--heading-font), var(--default-font), var(--button-font)); a Google Fonts link or a literal font-family bypasses them.',
        exempt: {
            'src/components/blocks/FleetList.astro': "swiper's own icon font (swiper-icons) for the carousel arrow glyph; it is an icon font, not a text face",
            'src/pages/list_data.astro': 'in-flight landing work (owner: keep untouched)',
        },
        find: (file) => {
            if (file.path === 'src/styles/_fonts.scss' || file.path.startsWith('src/styles/properties/')) return []
            const links = hits_in(file, [{ text: file.text, offset: 0 }], GOOGLE_FONTS)
            const literals = hits_in(file, css_regions(file).map(without_css_comments), FONT_FAMILY_LITERAL)
            return [...links, ...literals]
        },
    },
    {
        id: 'palette_off_meaning',
        kind: 'absolute',
        why: 'Security-status and meta-group colours have one meaning each: draw them with <SecurityStatus> or <MetaGroupTag>, or the icons. Using these tokens anywhere else lends the colour a different meaning.',
        exempt: {
            'src/components/blocks/FittingSlot.astro': "draws a module's meta group (Tech I/II/III, Storyline, Faction, Officer, Deadspace, Abyssal) on a fitting slot: game data in the game's colours, not a UI meaning",
        },
        find: (file) => {
            if (file.path.startsWith('src/components/icons/') || file.path.startsWith('src/styles/properties/')) return []
            if (COMPONENT_FILES('blocks/sde/SecurityStatus', 'blocks/sde/MetaGroupTag').includes(file.path)) return []
            // The .text-status-* definitions in _global.scss are the one place the security-status tokens are read directly.
            const text = file.path === 'src/styles/_global.scss' ? file.text.replace(TEXT_STATUS_BLOCK, (m) => m.replace(/[^\n]/g, ' ')) : file.text
            return hits_in(file, [{ text, offset: 0 }], OFF_MEANING_TOKEN)
        },
    },
    {
        id: 'local_semantic_colour',
        kind: 'ratchet',
        why: 'Semantic colours (warn, good, bad, success, danger) are defined once in src/styles/properties/_colors.scss; a component-local --x-warn definition forks that palette. Use the token it names.',
        find: (file) => {
            if (file.path === 'src/styles/properties/_colors.scss') return []
            return hits_in(file, css_regions(file).map(without_css_comments), LOCAL_SEMANTIC_DEFINITION)
        },
    },
]

/** Rules as enforced: a file in a rule's `exempt` map yields no hits. `RULE_DEFINITIONS` keeps the unfiltered matchers. */
export const with_exemptions = (r: ConventionRule): ConventionRule =>
    r.exempt ? { ...r, find: (file: SourceFile) => (Object.hasOwn(r.exempt!, file.path) ? [] : r.find(file)) } : r
export const RULES: ConventionRule[] = RULE_DEFINITIONS.map(with_exemptions)

/** Rules that carry exemptions, with the raw matcher, so a stale exemption (the file is gone or now clean) can be caught. */
export const EXEMPTIONS = RULE_DEFINITIONS.filter((r) => r.exempt).map((r) => ({ id: r.id, exempt: r.exempt!, find: r.find }))

export function rule(id: string): ConventionRule {
    const found = RULES.find((r) => r.id === id)
    if (!found) throw new Error(`unknown rule ${id}`)
    return found
}
