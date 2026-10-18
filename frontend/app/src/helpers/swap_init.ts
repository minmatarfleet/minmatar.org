/**
 * One place that wires up content htmx swaps in, for every page.
 *
 * - Alpine: its MutationObserver already initialises added nodes, and
 *   `Alpine.initTree` skips nodes it has seen (`_x_marker`), so calling it on
 *   the swap target is idempotent. Doing it on `htmx:afterSwap` initialises the
 *   new markup before htmx settles it, the moment the old per-page scripts did.
 * - Tooltips: one tippy delegate on <html> creates a tooltip the first time a
 *   `[data-tippy-content]` element is hovered, focused or touched, unless it
 *   already has one. That covers partials, Alpine `x-teleport`/`x-for` copies
 *   and ClientRouter navigations without a per-component `x-init`.
 *
 * Deliberately no `htmx.process`: htmx processes what it swaps in, and
 * re-processing a `hx-trigger="load"` element whose attributes changed fires
 * its request a second time.
 */

/** Elements that carry a tooltip; an empty attribute means "no tooltip". */
export const TOOLTIP_TARGET = '[data-tippy-content]:not([data-tippy-content=""])'

interface AlpineLike {
    initTree: (el: Element) => void;
}

type TippyDelegate = (root: Element, props: Record<string, unknown>) => unknown

export interface SwapInitWindow {
    document:                    Document;
    Alpine?:                     AlpineLike;
    tippy?:                      { delegate?: TippyDelegate };
    tippy_options?:              Record<string, unknown>;
    __minmatar_swap_init_bound?: boolean;
    __minmatar_tooltip_delegate?: boolean;
}

/** Initialise Alpine inside a swap target that is still in the document. */
export function init_swapped_alpine(win: SwapInitWindow, target: unknown) {
    const element = target as Element | null | undefined
    // An outerHTML swap detaches its target; Alpine's observer picks up the
    // replacement on its own.
    if (!element || !(element as Element).isConnected || !win.Alpine)
        return false

    win.Alpine.initTree(element)
    return true
}

/** Bind the tooltip delegate once tippy has loaded. Returns whether it is bound. */
export function bind_tooltip_delegate(win: SwapInitWindow): boolean {
    if (win.__minmatar_tooltip_delegate)
        return true

    const delegate = win.tippy?.delegate
    if (typeof delegate !== 'function')
        return false

    win.__minmatar_tooltip_delegate = true
    delegate(win.document.documentElement, {
        ...(win.tippy_options ?? {}),
        target: TOOLTIP_TARGET,
    })
    return true
}

export function bind_swap_init(win: SwapInitWindow) {
    if (win.__minmatar_swap_init_bound)
        return
    win.__minmatar_swap_init_bound = true

    const doc = win.document

    doc.addEventListener('htmx:afterSwap', (event: Event) => {
        init_swapped_alpine(win, (event as CustomEvent).detail?.target)
    })

    // tippy is a deferred CDN script; it has run by DOMContentLoaded.
    if (!bind_tooltip_delegate(win)) {
        if (doc.readyState === 'loading')
            doc.addEventListener('DOMContentLoaded', () => bind_tooltip_delegate(win), { once: true })
        else
            setTimeout(() => bind_tooltip_delegate(win))
    }
}
