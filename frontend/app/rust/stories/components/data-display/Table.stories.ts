import { expect, within } from 'storybook/test'
import Table from '@components/blocks/Table.astro'

const row = (fc: string, hull: string, pilots: number, isk: string) =>
    `<div class="flex flex-wrap items-center justify-between" role="listitem"><strong>${fc}</strong><span>${hull}</span><span>${pilots} pilots</span><span>${isk} ISK</span></div>`

const rows = [
    row("Kel'dar Atram", 'Cormorant Navy Issue', 38, '2.1B'),
    row('Rattini Pilot', 'Vexor Navy Issue', 24, '1.4B'),
    row('Hek Roamer', 'Rifter', 12, '180M'),
].join('')

// XFadeScroll's Alpine data (`edge_fade`) is defined by the site's footer scripts, which Storybook does not load.
// A copy keeps the scroller working in the browser; the test environment has no ResizeObserver, so it is skipped there.
const w = globalThis as any
if (!w.edge_fade) {
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

export default {
    title: 'Components/Data display/Table',
    component: Table,
    parameters: {
        docs: {
            description: {
                component: [
                    'A list-based "table": a `role="list"` BlockList wrapped in an edge-fading horizontal scroller. The caller slots in its own row elements (each row is a flex line); there are no columns. Use it for rows built from components such as order or product items. For a real header row with columns use DataGrid.',
                    '`width` is the minimum width before sideways scrolling kicks in; `responsive={false}` drops the scroller (use with `width="100%"` when rows already wrap). On phones the rows stack with a rule between them.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: { control: 'text', description: 'Space between rows; BlockList default when unset.' },
        responsive: { control: 'boolean', description: 'Wrap in XFadeScroll so the table scrolls sideways instead of overflowing.' },
        width: { control: 'text', description: 'Table width (a minimum, since the table scrolls). Use `100%` with `responsive: false`.' },
    },
    args: { responsive: true, width: '70rem', slots: { default: rows } },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const list = within(canvasElement).getByRole('list')
        await expect(list).toHaveClass('table')
        await expect(within(list).getAllByRole('listitem')).toHaveLength(3)
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeTruthy()
    },
}

export const NotResponsive = {
    name: 'Not responsive (full width)',
    args: { responsive: false, width: '100%' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeNull()
        await expect(within(canvasElement).getByRole('list')).toHaveClass('table')
    },
}

export const WideRows = {
    name: 'Wide (scrolls sideways)',
    args: { width: '90rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Cormorant Navy Issue')).toBeInTheDocument()
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeTruthy()
    },
}

export const SingleRow = {
    name: 'Single row',
    args: { slots: { default: row('Hek Roamer', 'Rifter', 12, '180M') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByRole('listitem')).toHaveLength(1)
    },
}

export const CustomAttributes = {
    name: 'Passthrough attributes',
    args: { id: 'fleets-table', 'aria-label': 'Recent fleets' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const list = within(canvasElement).getByRole('list', { name: 'Recent fleets' })
        await expect(list).toHaveAttribute('id', 'fleets-table')
    },
}
