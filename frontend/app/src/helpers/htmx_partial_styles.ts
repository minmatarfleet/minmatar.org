/**
 * Ship a partial's CSS with the partial.
 *
 * Astro renders a partial as `<!DOCTYPE html>`, then its <link>/<style> tags,
 * then the markup. htmx 1.9 picks a parser from the first tag. If that is a
 * <style>, it keeps everything; if it is a <link>, DOMParser hoists all the
 * leading stylesheet tags into <head> and htmx keeps only <body>, so the
 * partial's styles, and the styles of any component only the partial renders,
 * never reach the page. Which partials start with a <link> depends on how
 * Vite splits CSS chunks, so it changes from build to build.
 *
 * Before htmx swaps such a response in, this copies its stylesheets into the
 * document. It only adds rules the document does not already have, so the
 * page's own CSS is never re-declared later in the cascade (which could
 * reorder rules of equal specificity). Astro's ClientRouter drops the added
 * <style> elements on the next navigation because the new page's head does not
 * contain them.
 */

export const PARTIAL_STYLE_ATTRIBUTE = 'data-partial-style'

export interface PartialStylesheet {
    key:    string;
    href?:  string;
    css?:   string;
    dev_id?: string;
}

const STYLESHEET_SELECTOR = 'link[rel~="stylesheet"][href], style'

/** htmx swaps only the <body> of a full page; leave those alone. */
const is_full_page = (html: string): boolean => /<body/i.test(html)

/** Cheap check before parsing: does the response carry any stylesheet? */
export const has_stylesheets = (html: string): boolean => /<(?:link|style)\b/i.test(html)

function hash_text(text: string): string {
    let hash = 5381
    for (let i = 0; i < text.length; i++)
        hash = ((hash << 5) + hash + text.charCodeAt(i)) | 0
    return (hash >>> 0).toString(36) + text.length.toString(36)
}

/**
 * htmx 1.9 picks its parser by the first tag in the response. When that tag
 * is <style> or <script> it wraps the response in a <div>, so the stylesheets
 * stay in the swapped content and already apply. Only other first tags (an
 * Astro partial that starts with <link>) lose them to <head>.
 */
export function htmx_drops_stylesheets(html: string): boolean {
    const first_tag = /<([a-z][^\/\0>\x20\t\r\n\f]*)/i.exec(html)?.[1]?.toLowerCase()
    return first_tag !== 'style' && first_tag !== 'script'
}

/** Stylesheets in the part of a partial response that DOMParser puts in <head>. */
export function extract_partial_stylesheets(html: string, base_url: string): PartialStylesheet[] {
    if (!html || is_full_page(html) || !has_stylesheets(html) || !htmx_drops_stylesheets(html))
        return []

    const parsed = new DOMParser().parseFromString(html, 'text/html')
    const sheets: PartialStylesheet[] = []

    // A browser's parser hoists the leading tags into <head>, exactly the part
    // htmx drops. Parsers that don't (happy-dom in tests) leave them at the
    // start of <body>; treat that leading run the same way.
    const nodes = Array.from(parsed.head.querySelectorAll(STYLESHEET_SELECTOR))
    for (const child of Array.from(parsed.body.children)) {
        if (!child.matches(STYLESHEET_SELECTOR))
            break
        nodes.push(child)
    }

    nodes.forEach((node) => {
        if (node.tagName === 'LINK') {
            const href = new URL(node.getAttribute('href') as string, base_url).href
            sheets.push({ key: `link:${href}`, href })
            return
        }

        const css = node.textContent ?? ''
        if (!css.trim())
            return

        const dev_id = node.getAttribute('data-vite-dev-id') ?? undefined
        sheets.push({
            key: dev_id ? `dev:${dev_id}` : `style:${hash_text(css)}`,
            css,
            dev_id,
        })
    })

    return sheets
}

interface RuleLike {
    cssText:   string;
    cssRules?: ArrayLike<RuleLike>;
}

/** Grouping rules (@media, @supports, @layer, @container) are compared rule by rule. */
function is_grouping_rule(rule: RuleLike): boolean {
    return !!rule.cssRules && /^@(media|supports|layer|container)\b/i.test(rule.cssText)
}

function prelude(rule: RuleLike): string {
    return rule.cssText.slice(0, rule.cssText.indexOf('{')).trim()
}

/** Keys for every rule, with grouping rules flattened to `prelude{rule}`. */
export function rule_keys(rules: ArrayLike<RuleLike>, scope = '', keys: Set<string> = new Set()): Set<string> {
    for (let i = 0; i < rules.length; i++) {
        const rule = rules[i]
        if (is_grouping_rule(rule))
            rule_keys(rule.cssRules as ArrayLike<RuleLike>, `${scope}${prelude(rule)}{`, keys)
        else
            keys.add(`${scope}${rule.cssText}`)
    }
    return keys
}

/** CSS text with only the rules whose keys are not in `existing`. */
export function missing_rules_css(rules: ArrayLike<RuleLike>, existing: Set<string>, scope = ''): string {
    const out: string[] = []

    for (let i = 0; i < rules.length; i++) {
        const rule = rules[i]
        if (is_grouping_rule(rule)) {
            const inner = missing_rules_css(
                rule.cssRules as ArrayLike<RuleLike>,
                existing,
                `${scope}${prelude(rule)}{`,
            )
            if (inner)
                out.push(`${prelude(rule)} {\n${inner}\n}`)
        } else if (!existing.has(`${scope}${rule.cssText}`)) {
            out.push(rule.cssText)
        }
    }

    return out.join('\n')
}

/** Rules the document already has. Cross-origin sheets (CDN CSS) can't be read and are skipped. */
export function document_rule_keys(doc: Document): Set<string> {
    const keys = new Set<string>()
    for (const sheet of Array.from(doc.styleSheets)) {
        try {
            rule_keys(sheet.cssRules as unknown as ArrayLike<RuleLike>, '', keys)
        } catch {
            // SecurityError for cross-origin sheets
        }
    }
    return keys
}

function parse_rules(css: string): ArrayLike<RuleLike> | null {
    try {
        const sheet = new CSSStyleSheet()
        sheet.replaceSync(css)
        return sheet.cssRules as unknown as ArrayLike<RuleLike>
    } catch {
        return null
    }
}

function css_attribute_value(value: string): string {
    return typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(value) : value.replace(/["\\]/g, '\\$&')
}

function already_added(doc: Document, sheet: PartialStylesheet): boolean {
    if (doc.head.querySelector(`[${PARTIAL_STYLE_ATTRIBUTE}="${css_attribute_value(sheet.key)}"]`))
        return true

    if (sheet.dev_id && doc.querySelector(`style[data-vite-dev-id="${css_attribute_value(sheet.dev_id)}"]`))
        return true

    if (sheet.href) {
        return Array.from(doc.querySelectorAll<HTMLLinkElement>('link[rel~="stylesheet"]'))
            .some((link) => link.href === sheet.href)
    }

    return false
}

/** Append the rules of `css` the document lacks to `holder`. */
function fill_holder(doc: Document, holder: HTMLStyleElement, css: string) {
    const rules = parse_rules(css)
    // Without CSSOM parsing, fall back to the whole sheet: duplicated rules
    // are better than an unstyled partial.
    holder.textContent = rules ? missing_rules_css(rules, document_rule_keys(doc)) : css
}

/**
 * Add the stylesheets of a partial response to the document. Returns the keys
 * of the sheets it added (for tests and debugging).
 */
export function apply_partial_stylesheets(
    doc: Document,
    html: string,
    fetch_css: (href: string) => Promise<string> = (href) => fetch(href).then((r) => (r.ok ? r.text() : '')),
): string[] {
    const added: string[] = []

    for (const sheet of extract_partial_stylesheets(html, doc.baseURI)) {
        if (already_added(doc, sheet))
            continue

        // The holder doubles as the "seen" marker, even when every rule turns
        // out to exist already, so repeated swaps skip straight past it.
        const holder = doc.createElement('style')
        holder.setAttribute(PARTIAL_STYLE_ATTRIBUTE, sheet.key)
        doc.head.appendChild(holder)
        added.push(sheet.key)

        if (sheet.css !== undefined) {
            fill_holder(doc, holder, sheet.css)
        } else if (sheet.href) {
            fetch_css(sheet.href)
                .then((css) => { if (holder.isConnected && css) fill_holder(doc, holder, css) })
                .catch(() => {})
        }
    }

    return added
}

/** Install once per window; the listener lives on `document`, which ClientRouter keeps. */
export function bind_partial_styles(win: Window & { __minmatar_partial_styles_bound?: boolean }) {
    if (win.__minmatar_partial_styles_bound)
        return
    win.__minmatar_partial_styles_bound = true

    win.document.addEventListener('htmx:beforeSwap', (event: Event) => {
        const detail = (event as CustomEvent).detail
        if (!detail?.shouldSwap || !detail.xhr)
            return

        try {
            apply_partial_stylesheets(win.document, String(detail.xhr.responseText ?? ''))
        } catch (error) {
            console.error('partial styles', error)
        }
    })
}
