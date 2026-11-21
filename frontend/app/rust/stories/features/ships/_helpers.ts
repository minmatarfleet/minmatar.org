// Shared helpers for the Features/Ships stories.

/** The site defines `edge_fade` (XFadeScroll's Alpine data) in FooterScripts, which Storybook's head does not load. */
export const register_edge_fade = () => {
    const w = globalThis as any
    if (w.edge_fade) return
    w.edge_fade = () => ({
        init() {
            const el = (this as any).$el as HTMLElement
            const update = () => {
                el.classList.toggle('fade-start', el.scrollLeft > 0)
                el.classList.toggle('fade-end', el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
            }
            update()
            if (typeof ResizeObserver !== 'undefined') new ResizeObserver(update).observe(el)
            el.addEventListener('scroll', update, { passive: true })
        },
    })
}

/** Constrain a story to a card column, as the grids on the site do. */
export const in_column = (width: string) => (Story: () => unknown) =>
    `<div style="width: ${width}; max-width: 100%">${Story()}</div>`

export type PlayArgs = { canvasElement: HTMLElement }
