// Mounts server-rendered story HTML into the happy-dom document with the
// same Alpine build and plugins the site loads, so play functions can click
// toggles, open menus and switch tabs in vitest, not only in the browser.
import Alpine from 'alpinejs'
import persist from '@alpinejs/persist'
import collapse from '@alpinejs/collapse'
import focus from '@alpinejs/focus'
import anchor from '@alpinejs/anchor'
import mask from '@alpinejs/mask'
import intersect from '@alpinejs/intersect'

let started = false
export const alpine_errors: string[] = []

function start_alpine() {
    if (started)
        return
    started = true

    const win = window as any
    win.Alpine = Alpine
    // Globals the site's scripts define and components call from x-init.
    win.tippy = win.tippy ?? (() => ({ destroy() {}, setContent() {}, show() {}, hide() {} }))
    win.tippy_options = win.tippy_options ?? {}
    win.htmx = win.htmx ?? { process() {}, ajax() { return Promise.resolve() }, trigger() {} }

    ;(Alpine as any).setErrorHandler?.((error: unknown, el: Element, expression?: string) => {
        alpine_errors.push(`${expression ?? ''}: ${error instanceof Error ? error.message : String(error)}`)
    })

    document.body.setAttribute('x-data', '{ viewport_width: window.innerWidth, color_blind_mode: false }')
    Alpine.plugin(persist)
    Alpine.plugin(collapse)
    Alpine.plugin(focus)
    Alpine.plugin(anchor)
    Alpine.plugin(mask)
    Alpine.plugin(intersect)
    Alpine.start()
}

export async function mount_story(html: string): Promise<HTMLElement> {
    start_alpine()
    alpine_errors.length = 0

    const previous = document.getElementById('storybook-root')
    if (previous) {
        Alpine.destroyTree(previous)
        Alpine.mutateDom(() => previous.remove())
    }

    const root = document.createElement('div')
    root.id = 'storybook-root'
    root.innerHTML = html
    // Insert with Alpine's observer paused and initialise the tree once,
    // under the body's scope, as the site does on page load.
    Alpine.mutateDom(() => document.body.appendChild(root))
    Alpine.initTree(root)
    await Alpine.nextTick()
    await new Promise((resolve) => setTimeout(resolve, 0))
    return root
}
