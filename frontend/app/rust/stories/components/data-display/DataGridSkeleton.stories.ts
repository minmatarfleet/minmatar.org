import { expect, within } from 'storybook/test'
import DataGridSkeleton from '@components/blocks/DataGridSkeleton.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

// XFadeScroll's Alpine data (`edge_fade`) is defined by the site's footer scripts, which Storybook does not load.
const w = globalThis as any
if (!w.edge_fade) w.edge_fade = () => ({ init() {} })

export default {
    title: 'Components/Data display/DataGridSkeleton',
    component: DataGridSkeleton,
    parameters: {
        docs: {
            description: {
                component: [
                    'Loading state for a DataGrid: the real header and the same column `template`, with shimmering bars where the rows will be. Put it inside a LazyPartial (or any slot an htmx partial replaces) with the same `columns`, `template` and `rows` as the grid it stands in for, so the table arrives without the page jumping.',
                    '`media` marks columns that start with a portrait or icon square, `numeric` columns get a short right-aligned bar, and `pager` adds a bar where an HtmxPager will sit. With `stack`, phones drop the header like DataGrid does and the row becomes a card. The root carries `aria-busy="true"` and the rows are hidden from screen readers. Bars stop moving under reduced motion.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        columns: { control: 'object', description: 'Header labels, one per column (the same as the DataGrid it stands in for).' },
        template: { control: 'text', description: 'The shared `grid-template-columns` value.' },
        rows: { control: 'number', description: 'How many placeholder rows.' },
        media: { control: 'object', description: 'Column indexes that start with a portrait or icon square.' },
        numeric: { control: 'object', description: 'Column indexes whose bar is short and right-aligned.' },
        min_width: { control: 'text', description: 'Below this width the grid scrolls sideways, as DataGrid does.' },
        variant: radio_control(['compact', 'ledger'], 'The DataGrid variant it stands in for.'),
        stack: { control: 'boolean', description: 'On phones, hide the header and lay each row out as a card.' },
        pager: { control: 'boolean', description: 'A bar under the grid where an HtmxPager will be.' },
    },
    args: {
        columns: ['EVE time', 'What happened', 'Region'],
        template: '9rem minmax(0, 1fr) 8rem',
        rows: 6,
        media: [1],
        numeric: [2],
        min_width: '0',
        variant: 'ledger',
        stack: false,
        pager: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const root = canvasElement.querySelector('.data-grid-skeleton')
        await expect(root).toHaveAttribute('aria-busy', 'true')
        await expect(canvas.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['EVE time', 'What happened', 'Region'])
        await expect(canvasElement.querySelectorAll('.data-grid-skeleton__row')).toHaveLength(6)
        await expect(canvasElement.querySelectorAll('.skel-media')).toHaveLength(6)
    },
}

export const WithPager = {
    name: 'With pager bar',
    args: { pager: true, rows: 12 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.data-grid-skeleton__row')).toHaveLength(12)
        await expect(canvasElement.querySelector('.data-grid-skeleton__pager')).not.toBeNull()
    },
}

export const NoMedia = {
    name: 'Plain columns (no media)',
    args: {
        columns: ['Contract', 'Location', 'Volume', 'Reward'],
        template: '1.4fr 1fr 6rem 8rem',
        media: [],
        numeric: [2, 3],
        variant: 'compact',
        rows: 4,
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.skel-media')).toHaveLength(0)
        const numeric_cells = canvasElement.querySelectorAll('.data-grid-skeleton__row .data-grid-numeric')
        await expect(numeric_cells).toHaveLength(8)
    },
}

export const Stacked = {
    name: 'Stacked on phones (stack)',
    args: { stack: true, pager: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.data-grid')).toHaveClass('data-grid--stack')
    },
}
