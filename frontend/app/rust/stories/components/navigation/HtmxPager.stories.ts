import { expect, within, userEvent, waitFor } from 'storybook/test'
// Stories render HtmxPager through a wrapper: its url_for prop is a function.
import HtmxPager from '../../../components/HtmxPagerExample.astro'
import Button from '@components/blocks/Button.astro'

type Ctx = { canvasElement: HTMLElement }

const url_pattern = '/partials/fleet_history_component?page={page}'

const partial = (page: number) =>
    `<ul id="fleet-list"><li>Fleet page ${page}: Strategic fleet in Amamake</li></ul>`

export default {
    title: 'Components/Navigation/HtmxPager',
    component: HtmxPager,
    parameters: {
        rust: { covers: 'blocks/HtmxPager' },
        docs: {
            description: {
                component: [
                    'Pager for a list fed by an htmx partial: each button requests another page and swaps it into `target`. With `total_pages` it shows Previous / Next (disabled at the ends) after a status line; with `has_more` (total unknown) it shows Newer / Older around "Page N", each only when that page exists, and nothing at all on a lone first page.',
                    '`url_for` builds the partial URL for a page number. `request` adds attributes to every request (`hx-include`, `hx-select`) and its `hx-target` / `hx-swap` win over `target` / `swap`. The `status` slot replaces "Page N" and `actions` adds buttons before Previous / Next (an export, say).',
                    'Rust runs htmx against mocked endpoints (`parameters.htmx`), so the swap stories answer from a fixture. A pager with a single page renders only its status line.',
                ].join('\n\n'),
            },
        },
        htmx: {
            '/partials/fleet_history_component': (url: URL) => partial(Number(url.searchParams.get('page'))),
        },
    },
    argTypes: {
        page: { control: 'number', description: 'Current page, starting at 1.' },
        url_pattern: { control: 'text', description: 'Stories only: the partial URL with `{page}`. On a page, pass `url_for`, a function `(page) => url`.' },
        total_pages: { control: 'number', description: 'Known page count: switches to Previous / Next mode.' },
        has_more: { control: 'boolean', description: 'Without a total: whether an older page exists (Newer / Older mode).' },
        target: { control: 'text', description: 'CSS selector `hx-target` of the swap.' },
        swap: { control: 'text', description: '`hx-swap` strategy; `outerHTML` replaces the target.' },
        request: { control: 'object', description: 'Extra attributes on every page button, e.g. `hx-include`, `hx-select`.' },
        gap: { control: 'text', description: 'Gap between the status and the buttons (CSS length or token).' },
        buttons_gap: { control: 'text', description: 'Gap between the buttons.' },
        class: { control: 'text', description: 'Extra classes on the pager root.' },
    },
    args: {
        page: 2,
        url_pattern,
        total_pages: 5,
        has_more: false,
        target: '#fleet-list',
        swap: 'outerHTML',
        request: {},
        buttons_gap: 'var(--space-3xs)',
    },
}

export const Default = {
    name: 'Previous / Next (total pages)',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByText('Page 2')).toBeVisible())
        const previous = canvas.getByRole('button', { name: 'Previous' })
        const next = canvas.getByRole('button', { name: 'Next' })
        await expect(previous).toHaveAttribute('hx-get', '/partials/fleet_history_component?page=1')
        await expect(next).toHaveAttribute('hx-get', '/partials/fleet_history_component?page=3')
        await expect(next).toHaveAttribute('hx-target', '#fleet-list')
        await expect(next).toHaveAttribute('hx-swap', 'outerHTML')
        await expect(previous).toBeEnabled()
        await expect(next).toBeEnabled()
    },
}

export const FirstPage = {
    name: 'First page: Previous disabled',
    args: { page: 1 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Previous' })).toBeDisabled()
        await expect(canvas.getByRole('button', { name: 'Next' })).toBeEnabled()
        await expect(canvas.getByRole('button', { name: 'Next' })).toHaveAttribute('hx-get', '/partials/fleet_history_component?page=2')
    },
}

export const LastPage = {
    name: 'Last page: Next disabled',
    args: { page: 5 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Next' })).toBeDisabled()
        await expect(canvas.getByRole('button', { name: 'Previous' })).toBeEnabled()
        await waitFor(() => expect(canvas.getByText('Page 5')).toBeVisible())
    },
}

export const SinglePage = {
    name: 'Single page: status only',
    args: { page: 1, total_pages: 1 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByText('Page 1')).toBeVisible())
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const NewerOlder = {
    name: 'Newer / Older (has_more)',
    args: { page: 3, total_pages: undefined, has_more: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: /Newer/ })).toHaveAttribute('hx-get', '/partials/fleet_history_component?page=2')
        await expect(canvas.getByRole('button', { name: /Older/ })).toHaveAttribute('hx-get', '/partials/fleet_history_component?page=4')
        await waitFor(() => expect(canvas.getByText('Page 3')).toBeVisible())
        await expect(canvas.queryByRole('button', { name: 'Previous' })).toBeNull()
    },
}

export const NewerOlderFirstPage = {
    name: 'Has more, first page: only Older',
    args: { page: 1, total_pages: undefined, has_more: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('button', { name: /Newer/ })).toBeNull()
        await waitFor(() => expect(canvas.getByRole('button', { name: /Older/ })).toBeVisible())
    },
}

export const NewerOlderLastPage = {
    name: 'No more, later page: only Newer',
    args: { page: 4, total_pages: undefined, has_more: false },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByRole('button', { name: /Newer/ })).toBeVisible())
        await expect(canvas.queryByRole('button', { name: /Older/ })).toBeNull()
    },
}

export const NothingToPage = {
    name: 'Lone first page renders nothing',
    args: { page: 1, total_pages: undefined, has_more: false },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
        await expect(canvasElement.querySelector('.htmx-pager')).toBeNull()
    },
}

export const RequestAttributes = {
    name: 'Request attributes (hx-include, hx-select)',
    args: {
        target: undefined,
        request: { 'hx-target': '#fleet-list', 'hx-select': '#fleet-list', 'hx-swap': 'outerHTML', 'hx-include': '#fleet-filters' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const next = within(canvasElement).getByRole('button', { name: 'Next' })
        await expect(next).toHaveAttribute('hx-include', '#fleet-filters')
        await expect(next).toHaveAttribute('hx-select', '#fleet-list')
        await expect(next).toHaveAttribute('hx-target', '#fleet-list')
    },
}

export const StatusAndActions = {
    name: 'Status and actions slots',
    args: {
        slots: {
            status: '<small>Showing 26–50 of 112 fleets</small>',
            actions: { component: Button, props: { size: 'sm', color: 'transparent', href: '/fleets/export/' }, slots: { default: 'Export CSV' } },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByText('Showing 26–50 of 112 fleets')).toBeVisible())
        await expect(canvas.queryByText('Page 2')).toBeNull()
        await expect(canvas.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('href', '/fleets/export/')
        await waitFor(() => expect(canvas.getByRole('button', { name: 'Next' })).toBeVisible())
    },
}

export const SwapsThePage = {
    name: 'Swaps the list on click',
    tags: ['browser'],
    args: { target: '#fleet-list' },
    // The list the pager swaps, above it as on a page.
    decorators: [(Story: () => unknown) => `${partial(2)}${Story()}`],
    parameters: {
        htmx: {
            '/partials/fleet_history_component': (url: URL) => partial(Number(url.searchParams.get('page'))),
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'Next' }))
        await waitFor(() => {
            const requests = (window as any).__rust_htmx_requests ?? []
            expect(requests.some((request: { url: string }) => request.url.includes('page=3'))).toBe(true)
        })
        await waitFor(() => expect(canvas.getByText(/Fleet page 3/)).toBeVisible())
    },
}
