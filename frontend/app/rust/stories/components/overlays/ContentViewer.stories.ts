import { expect, userEvent, waitFor } from 'storybook/test'
import ContentViewer from '@components/blocks/ContentViewer.astro'

type Ctx = { canvasElement: HTMLElement }

// happy-dom (the vitest DOM) returns the server-rendered value for attributes Alpine rebinds; read the live list.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

const dialog = (canvasElement: HTMLElement) => canvasElement.querySelector('dialog.content-viewer') as HTMLDialogElement

// What a ContentViewerLink sends on a plain click.
const open = (title: string, href: string) =>
    window.dispatchEvent(new CustomEvent('content-viewer-open', { detail: { title, href } }))

export default {
    title: 'Components/Overlays/ContentViewer',
    component: ContentViewer,
    parameters: {
        docs: {
            description: {
                component: [
                    'Reads, plays or shows a post or guide without leaving the page. Put one `ContentViewer` on a page and wrap each card or link in a `ContentViewerLink`: a plain click opens the viewer and htmx loads `/partials/content_viewer_component` into it; a ctrl/cmd/middle click still opens the full page.',
                    'The partial picks the body by kind: a video post plays inline (YouTube, privacy mode, autoplay since it was clicked), a propaganda poster is shown whole and zooms on click, an article or a guide reads like its page. A members-only or missing post shows a message and the "Open full page" link.',
                    'Every image in the body zooms: a click opens it full screen inside the dialog, where it can be pinched, wheeled, dragged and double-tapped (up to 600%), with − / + / Fit buttons. Escape leaves the zoom before the viewer. Posters, gallery pages and comic panels are made to be read this way.',
                    'It is a native `<dialog>`: top layer, focus trap, Escape. On desktop it is a panel sized to its kind (wide for video, a reading column for text); at 48rem and below it fills the screen. Opening adds a history entry, so Back closes it instead of leaving the page. Closing empties the body, which stops a video.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        class: { control: 'text', description: 'Extra classes on the dialog.' },
    },
    args: {},
}

export const Default = {
    name: 'Closed until a link opens it',
    play: async ({ canvasElement }: Ctx) => {
        const viewer = dialog(canvasElement)
        await expect(viewer).not.toBeNull()
        await expect(viewer.hasAttribute('open')).toBe(false)
        await expect(viewer).toHaveAttribute('aria-labelledby', 'content-viewer-title')
        await expect(canvasElement.querySelector('#content-viewer-body')).not.toBeNull()
    },
}

export const Opens = {
    name: 'Opens with the title and a link to the page',
    play: async ({ canvasElement }: Ctx) => {
        const viewer = dialog(canvasElement)
        open('The Goonswarm Effect - YC 128', '/alliance/propaganda/the-goonswarm-effect-251')
        await waitFor(() => expect(viewer.hasAttribute('open')).toBe(true))
        await waitFor(() => expect(viewer.querySelector('#content-viewer-title')?.textContent).toBe('The Goonswarm Effect - YC 128'))
        await expect(attr(viewer.querySelector('.content-viewer__open') as Element, 'href')).toBe('/alliance/propaganda/the-goonswarm-effect-251')
        // Loading until the partial lands.
        await expect(attr(viewer, 'data-loading')).toBe('true')
    },
}

export const CloseButton = {
    name: 'Close button empties and closes it',
    play: async ({ canvasElement }: Ctx) => {
        const viewer = dialog(canvasElement)
        open('EvE Online - The Cope', '/alliance/propaganda/the-cope-275')
        await waitFor(() => expect(viewer.hasAttribute('open')).toBe(true))
        const body = viewer.querySelector('#content-viewer-body') as HTMLElement
        body.innerHTML = '<div class="content-viewer-content" data-kind="video"><p>Playing</p></div>'
        const alpine = (window as any).Alpine.$data(viewer)
        await expect(alpine.is_open).toBe(true)
        ;(viewer.querySelector('.content-viewer__close') as HTMLElement).click()
        await waitFor(() => expect(alpine.is_open).toBe(false))
        await expect(body.innerHTML).toBe('')
        // happy-dom's <dialog> keeps `open` after close(); the browser run checks the element itself.
        if (!navigator.userAgent.includes('HappyDOM')) await waitFor(() => expect(viewer.open).toBe(false))
    },
}

export const LoadsAPost = {
    name: 'Loads a poster through htmx',
    // htmx swaps the mocked partial in; that needs the browser.
    tags: ['browser'],
    parameters: {
        htmx: {
            '/partials/content_viewer_component': {
                body: '<div class="content-viewer-content" data-kind="image" data-title="Stamped" data-href="/alliance/propaganda/stamped-240"><figure><img alt="Stamped" src="/images/propaganda-cover.jpg" /></figure></div>',
                delay: 200,
            },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const viewer = dialog(canvasElement)
        const link = document.createElement('a')
        link.href = '/alliance/propaganda/stamped-240'
        link.setAttribute('hx-get', '/partials/content_viewer_component/?post=240')
        link.setAttribute('hx-target', '#content-viewer-body')
        link.textContent = 'Stamped'
        link.addEventListener('click', () => open('', '/alliance/propaganda/stamped-240'))
        canvasElement.append(link)
        ;(window as any).htmx.process(link)
        await userEvent.click(link)
        await waitFor(() => expect(viewer.querySelector('[data-kind="image"]')).not.toBeNull(), { timeout: 4000 })
        await waitFor(() => expect(viewer.querySelector('#content-viewer-title')?.textContent).toBe('Stamped'))
        await expect((window as any).Alpine.$data(viewer).loading).toBe(false)
    },
}

export const ZoomsAnImage = {
    name: 'A click on an image zooms it; Escape leaves the zoom first',
    play: async ({ canvasElement }: Ctx) => {
        const viewer = dialog(canvasElement)
        open('Stamped', '/alliance/propaganda/stamped-240')
        await waitFor(() => expect(viewer.hasAttribute('open')).toBe(true))
        const body = viewer.querySelector('#content-viewer-body') as HTMLElement
        body.innerHTML = '<div class="content-viewer-content" data-kind="image"><figure><img alt="Stamped" src="/images/propaganda-cover.jpg" /></figure></div>'
        const alpine = (window as any).Alpine.$data(viewer)
        ;(body.querySelector('img') as HTMLElement).click()
        await waitFor(() => expect(alpine.zoom.src).toContain('/images/propaganda-cover.jpg'))
        alpine.zoom_to(3)
        await expect(alpine.zoom.scale).toBe(3)
        alpine.zoom_to(99)
        await expect(alpine.zoom.scale).toBe(6)
        alpine.zoom_to(1)
        await expect([alpine.zoom.x, alpine.zoom.y]).toEqual([0, 0])
        alpine.escape()
        await expect(alpine.zoom.src).toBe('')
        await expect(alpine.is_open).toBe(true)
        alpine.escape()
        await waitFor(() => expect(alpine.is_open).toBe(false))
    },
}
