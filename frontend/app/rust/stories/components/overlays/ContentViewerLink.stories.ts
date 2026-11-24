import { expect, waitFor } from 'storybook/test'
import ContentViewerLink from '@components/blocks/ContentViewerLink.astro'

type Ctx = { canvasElement: HTMLElement }

const link = (canvasElement: HTMLElement) => canvasElement.querySelector('a.content-viewer-link') as HTMLAnchorElement

// Records content-viewer-open events (what the page's ContentViewer listens for).
function listen() {
    const seen: any[] = []
    const on = (event: Event) => seen.push((event as CustomEvent).detail)
    window.addEventListener('content-viewer-open', on)
    return { seen, stop: () => window.removeEventListener('content-viewer-open', on) }
}

const click = (el: HTMLElement, init: MouseEventInit = {}) => {
    const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...init })
    el.dispatchEvent(event)
    return event
}

export default {
    title: 'Components/Overlays/ContentViewerLink',
    component: ContentViewerLink,
    parameters: {
        docs: {
            description: {
                component: [
                    'Opens a page in the page\'s `ContentViewer`. Wrap a card, a thumbnail or a headline in it: it renders a real link to the full page (`href`), so new tabs, ctrl/cmd/middle clicks and no-JS visitors still land on the page, and a plain click opens the viewer and loads the content with htmx.',
                    'Any `href` the viewer can show opens in it: a post, a guide, a Warzone or Amamake Market report, a newsletter, Our values or a chapter of Our story (the list is `@helpers/content_viewer_sources`). Any other `href` is a plain link. `post` (a post id) or `guide` (a guide slug) name the content directly; `title` shows in the viewer\'s header while it loads. Classes and attributes pass through, so it can be the card itself.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        href: { control: 'text', description: 'The full page: where a new tab, a modified click or no-JS goes. A viewable page opens in the viewer.' },
        post: { control: 'number', description: 'A post id to open in the viewer.' },
        guide: { control: 'text', description: 'A guide slug to open in the viewer.' },
        title: { control: 'text', description: 'Shown in the viewer header while the content loads.' },
        class: { control: 'text', description: 'Classes on the link (it can be the card itself).' },
    },
    args: {
        href: '/alliance/propaganda/eve-online---the-cope-275',
        post: 275,
        title: 'EvE Online - The Cope - The Imperium Retreats',
        slots: { default: 'EvE Online - The Cope - The Imperium Retreats' },
    },
}

export const Post = {
    name: 'A post',
    play: async ({ canvasElement }: Ctx) => {
        const a = link(canvasElement)
        await expect(a).toHaveAttribute('href', '/alliance/propaganda/eve-online---the-cope-275')
        await expect(a.getAttribute('hx-get')).toContain('/partials/content_viewer_component/?source=post&id=275')
        await expect(a).toHaveAttribute('hx-target', '#content-viewer-body')
        await expect(a.getAttribute('hx-trigger')).toBe('content-viewer-load')
    },
}

export const Guide = {
    name: 'A guide',
    args: { href: '/learning/guides/onboarding-first-fleet/', post: undefined, guide: 'onboarding-first-fleet', title: 'Your first fleet', slots: { default: 'Your first fleet' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(link(canvasElement).getAttribute('hx-get')).toContain('?source=guide&id=onboarding-first-fleet')
    },
}

export const Report = {
    name: 'A report, from its href',
    args: { href: '/warzone/', post: undefined, title: 'Frontline Report', slots: { default: 'Frontline Report' } },
    play: async ({ canvasElement }: Ctx) => {
        const a = link(canvasElement)
        await expect(a).toHaveAttribute('href', '/warzone/')
        await expect(a.getAttribute('hx-get')).toMatch(/\?source=warzone&id=[\w-]+$/)
    },
}

export const Values = {
    name: 'Our values, from its href',
    args: { href: '/alliance/values/', post: undefined, title: 'Our values', slots: { default: 'Our values' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(link(canvasElement).getAttribute('hx-get')).toContain('?source=values')
    },
}

export const PlainLink = {
    name: 'Any other page: a plain link',
    args: { href: '/alliance/content/', post: undefined, title: '', slots: { default: 'All our content' } },
    play: async ({ canvasElement }: Ctx) => {
        const a = link(canvasElement)
        await expect(a).toHaveAttribute('href', '/alliance/content/')
        await expect(a.hasAttribute('hx-get')).toBe(false)
    },
}

export const OpensOnPlainClick = {
    name: 'A plain click opens the viewer, a ctrl click does not',
    play: async ({ canvasElement }: Ctx) => {
        const a = link(canvasElement)
        const { seen, stop } = listen()
        // Record whether the link's own handler cancelled the click, then stop
        // the navigation so the story page stays put.
        const cancelled: boolean[] = []
        const record = (event: Event) => { cancelled.push(event.defaultPrevented); event.preventDefault() }
        // The story root is shared with every story the browser run plays
        // after this one: the listener must go, or their clicks are cancelled.
        canvasElement.addEventListener('click', record)
        try {
            click(a, { ctrlKey: true })
            await new Promise((resolve) => setTimeout(resolve, 50))
            await expect(seen).toHaveLength(0)
            await expect(cancelled[0]).toBe(false)
            click(a)
            await waitFor(() => expect(seen).toHaveLength(1))
            await expect(cancelled[1]).toBe(true)
            await expect(seen[0]).toEqual({ title: 'EvE Online - The Cope - The Imperium Retreats', href: '/alliance/propaganda/eve-online---the-cope-275' })
        } finally {
            canvasElement.removeEventListener('click', record)
            stop()
        }
    },
}
