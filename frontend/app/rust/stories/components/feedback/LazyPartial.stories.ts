import { expect, waitFor, within } from 'storybook/test'
import LazyPartial from '@components/blocks/LazyPartial.astro'
import { radio_control } from '../../_controls'

const requests = () => ((window as any).__rust_htmx_requests ?? []) as { url: string }[]

export default {
    title: 'Components/Feedback/LazyPartial',
    component: LazyPartial,
    parameters: {
        docs: {
            description: {
                component: [
                    'A slot that fetches a server-rendered partial once and swaps it in, showing its children (a skeleton or "Loading...") until then. This is how deferred sections are loaded without client-side data fetching.',
                    '`trigger="load"` fetches with the page, `"reveal"` waits until the slot scrolls into view (or its dialog opens). `hx-target="this"` with `hx-disinherit` stops htmx inheriting a parent form\'s target; `aria-busy` flips to `false` after the request, success or failure.',
                    'Never `htmx.process()` the slot again, that fires `load` twice.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        url: { control: 'text', description: 'Partial URL to GET.' },
        trigger: radio_control(['load', 'reveal'], '`load` fetches immediately, `reveal` when scrolled into view.'),
        swap: radio_control(['innerHTML', 'outerHTML'], '`innerHTML` keeps the slot element; `outerHTML` replaces it.'),
        indicator: { control: 'text', description: 'Selector of the busy indicator; `false` skips the page loader.' },
        after_request: { control: 'text', description: 'Script for `hx-on--after-request` (`this` is the slot).' },
        class: { control: 'text', description: 'Class for the slot element.' },
    },
    args: {
        url: '/partials/structure_holdings_component/?id=1048464431313',
        trigger: 'load',
        swap: 'innerHTML',
        indicator: '.loader',
        after_request: '',
        slots: { default: '<p>Loading structure holdings...</p>' },
    },
}

export const Default = {
    parameters: { htmx: { '/partials/structure_holdings_component': { body: '<p>12 hulls stored in Amamake</p>', delay: 400 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot).toHaveAttribute('hx-get', '/partials/structure_holdings_component/?id=1048464431313')
        await expect(slot).toHaveAttribute('hx-trigger', 'load')
        await expect(slot).toHaveAttribute('hx-target', 'this')
        await expect(slot).toHaveAttribute('hx-disinherit', 'hx-target')
        await expect(slot).toHaveAttribute('hx-swap', 'innerHTML')
        await expect(slot).toHaveAttribute('hx-indicator', '.loader')
        await expect(slot).toHaveAttribute('aria-live', 'polite')
        await expect(within(canvasElement).getByText('Loading structure holdings...')).toBeVisible()
    },
}

export const Busy = {
    name: 'Busy while loading',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot).toHaveAttribute('aria-busy', 'true')
        await expect(slot.getAttribute('hx-on--after-request')).toContain("setAttribute('aria-busy', 'false')")
    },
}

export const SwapsInPartial = {
    name: 'Swaps the partial in',
    tags: ['browser'],
    parameters: { htmx: { '/partials/structure_holdings_component': { body: '<p>12 hulls stored in Amamake</p>', delay: 400 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByText('12 hulls stored in Amamake')).toBeVisible(), { timeout: 4000 })
        await expect(canvas.queryByText('Loading structure holdings...')).toBeNull()
        await expect(canvasElement.querySelector('[hx-get]')).toHaveAttribute('aria-busy', 'false')
        await expect(requests().filter((r) => r.url.startsWith('/partials/structure_holdings_component'))).toHaveLength(1)
    },
}

export const RevealTrigger = {
    name: 'Fetch on reveal',
    args: { trigger: 'reveal', url: '/partials/fleet_history_component/' },
    parameters: { htmx: { '/partials/fleet_history_component': { body: '<p>Last 20 fleets</p>', delay: 200 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot).toHaveAttribute('hx-trigger', 'intersect once')
        await expect(slot).toHaveAttribute('hx-get', '/partials/fleet_history_component/')
    },
}

export const OuterHtmlSwap = {
    name: 'Replaces itself (outerHTML)',
    args: { swap: 'outerHTML', url: '/partials/mentor_classes_component', slots: { default: '<p>Loading classes...</p>' } },
    tags: ['browser'],
    parameters: { htmx: { '/partials/mentor_classes_component': { body: '<ul><li>Basic Frigate Piloting</li></ul>', delay: 300 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot).toHaveAttribute('hx-swap', 'outerHTML')
        await waitFor(() => expect(within(canvasElement).getByText('Basic Frigate Piloting')).toBeVisible(), { timeout: 4000 })
        await expect(canvasElement.querySelector('[hx-get]')).toBeNull()
    },
}

export const RequestFails = {
    name: 'Request fails (aria-busy still clears)',
    tags: ['browser'],
    parameters: { htmx: { '/partials/structure_holdings_component': { status: 500, body: '', delay: 300 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await waitFor(() => expect(slot).toHaveAttribute('aria-busy', 'false'), { timeout: 4000 })
        // Nothing was swapped, so the fallback content is still there.
        await expect(within(canvasElement).getByText('Loading structure holdings...')).toBeVisible()
    },
}

export const AfterRequestScript = {
    name: 'After-request script',
    args: { after_request: "this.classList.add('is-loaded')" },
    tags: ['browser'],
    parameters: { htmx: { '/partials/structure_holdings_component': { body: '<p>Done</p>', delay: 200 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot.getAttribute('hx-on--after-request')).toContain("classList.add('is-loaded')")
        await waitFor(() => expect(slot).toHaveClass('is-loaded'), { timeout: 4000 })
    },
}

export const WithoutIndicator = {
    name: 'No page loader',
    args: { indicator: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('[hx-get]') as HTMLElement
        await expect(slot).not.toHaveAttribute('hx-indicator')
    },
}
