import { expect, userEvent, waitFor, within } from 'storybook/test'
import Tippy from '@components/blocks/Tippy.astro'
import FlexInline from '@components/compositions/FlexInline.astro'

export default {
    title: 'Components/Overlays/Tippy',
    component: Tippy,
    parameters: {
        docs: {
            description: {
                component: [
                    'A tooltip trigger. It renders its slot inside `element` (a `span` by default). Without `partial` it is a plain wrapper and the tooltip text comes from the `data-tippy-content` attribute you pass (the site\'s tippy script, `tippy_options`, attaches tippy to every `[data-tippy-content]`).',
                    'With `partial` the tooltip is loaded lazily: the first show fetches `partial` (a server-rendered component route) with htmx and swaps it in, with a "Loading" placeholder and the popper repositioned after the request. `show_delay`/`hide_delay` (ms) are written to `data-tippy-delay`. Use it for rich or expensive hover cards (a pilot card, a fitting); plain text tooltips are cheaper with a bare `data-tippy-content`.',
                    'The tooltip itself appears only in a browser with the `tippy` global loaded, so stories assert the rendered attributes in vitest and the hover behaviour in tagged `browser` stories.',
                ].join('\n\n'),
            },
        },
        layout: 'centered',
    },
    argTypes: {
        element: { control: 'text', description: 'HTML tag used for the trigger wrapper.' },
        partial: { control: 'text', description: 'Component route to load into the tooltip with htmx on first show. Omit for a static tooltip.' },
        height: { control: 'text', description: 'Reserved height of the tooltip (currently unused by the component).' },
        width: { control: 'text', description: 'Reserved width of the tooltip (currently unused by the component).' },
        show_delay: { control: 'number', description: 'Milliseconds before the tooltip shows (partial mode).' },
        hide_delay: { control: 'number', description: 'Milliseconds before the tooltip hides (partial mode).' },
    },
    args: {
        element: 'span',
        show_delay: 1000,
        hide_delay: 200,
        slots: { default: 'Rifter' },
    },
}

// A static tooltip: the text is a plain `data-tippy-content` attribute. (Not in the meta args: it would
// override the lazy `partial` content, because attributes are spread after it.)
const STATIC = { 'data-tippy-content': 'Rifter, Minmatar frigate' }

export const Default = {
    args: STATIC,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByText('Rifter')
        await expect(trigger.tagName).toBe('SPAN')
        await expect(trigger).toHaveAttribute('data-tippy-content', 'Rifter, Minmatar frigate')
        // Without `partial` no delay or HTML mode is set.
        await expect(trigger).not.toHaveAttribute('data-tippy-allowhtml')
    },
}

// The site's footer script attaches tippy to every `[data-tippy-content]` on page load; stories do it per play.
const attach_tippy = (root: HTMLElement) =>
    (window as any).tippy(root.querySelectorAll('[data-tippy-content]'), (window as any).tippy_options)

export const HoverShowsTooltip = {
    name: 'Hover shows the tooltip',
    tags: ['browser'],
    args: STATIC,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        attach_tippy(canvasElement)
        await userEvent.hover(within(canvasElement).getByText('Rifter'))
        const tooltip = await waitFor(() => {
            const root = document.querySelector('[data-tippy-root]')
            if (!root) throw new Error('tooltip not shown yet')
            return root as HTMLElement
        }, { timeout: 4000 })
        await expect(tooltip).toHaveTextContent('Rifter, Minmatar frigate')
    },
}

export const OtherElement = {
    name: 'Custom wrapper element',
    args: { element: 'strong', 'data-tippy-content': 'Stabber, Minmatar cruiser', slots: { default: 'Stabber' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByText('Stabber')
        await expect(trigger.tagName).toBe('STRONG')
        await expect(trigger).toHaveAttribute('data-tippy-content', 'Stabber, Minmatar cruiser')
    },
}

export const LazyPartial = {
    name: 'Lazy partial tooltip',
    args: { partial: '/partials/pilot_card_component', show_delay: 300, hide_delay: 100, slots: { default: 'Kel’dar Atram' } },
    parameters: { htmx: { '/partials/pilot_card_component': '<p>Kel’dar Atram, CEO of Rattini Tribe</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByText(/Kel.dar Atram/)
        await expect(trigger).toHaveAttribute('data-tippy-allowhtml', 'true')
        await expect(trigger).toHaveAttribute('data-tippy-delay', '[300, 100]')
        // The tooltip body is htmx markup that fetches the partial and falls back to "Loading".
        const content = trigger.getAttribute('data-tippy-content') as string
        await expect(content).toContain('hx-get=')
        await expect(content).toContain('/partials/pilot_card_component')
        await expect(content).toContain('hx-trigger="intersect"')
    },
}

export const DefaultDelays = {
    name: 'Default delays',
    args: { partial: '/partials/fitting_card_component', slots: { default: 'Fleet Rifter (Armor)' } },
    parameters: { htmx: { '/partials/fitting_card_component': '<p>Fleet Rifter (Armor)</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Fleet Rifter (Armor)')).toHaveAttribute('data-tippy-delay', '[1000, 200]')
    },
}

export const LazyPartialLoads = {
    name: 'Partial loads on hover',
    tags: ['browser'],
    args: { partial: '/partials/pilot_card_component', show_delay: 0, hide_delay: 100, slots: { default: 'Kel’dar Atram' } },
    parameters: { htmx: { '/partials/pilot_card_component': { body: '<p>Kel’dar Atram, CEO of Rattini Tribe</p>', delay: 200 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        attach_tippy(canvasElement)
        await userEvent.hover(within(canvasElement).getByText(/Kel.dar Atram/))
        await waitFor(() => expect(document.querySelector('[data-tippy-root]')).toHaveTextContent(/CEO of Rattini Tribe/), { timeout: 4000 })
        await expect((window as any).__rust_htmx_requests.length).toBeGreaterThan(0)
    },
}

export const InlineInRow = {
    name: 'Inline in a row of triggers',
    args: {
        slots: {
            default: [
                { component: Tippy, props: { 'data-tippy-content': 'Rifter' }, slots: { default: 'Rifter' } },
                { component: Tippy, props: { 'data-tippy-content': 'Stabber' }, slots: { default: 'Stabber' } },
                { component: Tippy, props: { 'data-tippy-content': 'Hurricane' }, slots: { default: 'Hurricane' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('[data-tippy-content]').length).toBeGreaterThanOrEqual(3)
    },
}
