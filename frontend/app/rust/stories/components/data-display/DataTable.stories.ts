import { expect, userEvent, waitFor, within } from 'storybook/test'
import DataTable from '@components/blocks/DataTable.astro'
import { radio_control } from '../../_controls'

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

const columns = [
    { key: 'fleet', label: 'Fleet', sortable: true },
    { key: 'hull', label: 'Hull', sortable: true },
    { key: 'pilots', label: 'Pilots', numeric: true, sortable: true },
    { key: 'isk', label: 'SRP paid (ISK)', numeric: true, sortable: true },
    { key: 'actions', label: 'Actions', hidden_label: true },
]

const fleets: [string, string, number, number][] = [
    ['Fleet 94', 'Cormorant Navy Issue', 38, 2140000000],
    ['Fleet 93', 'Vexor Navy Issue', 24, 1410000000],
    ['Fleet 92', 'Rifter', 12, 180000000],
    ['Fleet 91', 'Stabber', 41, 3020000000],
]

const row = ([fleet, hull, pilots, isk]: [string, string, number, number]) =>
    `<tr><td data-sort-fleet="${fleet.replace(/\D/g, '')}">${fleet}</td><td>${hull}</td><td class="data-table__numeric">${pilots}</td><td class="data-table__numeric" data-sort-isk="${isk}">${isk.toLocaleString('en-US')}</td><td class="data-table__actions"><a href="#">Open</a></td></tr>`

const rows = fleets.map(row).join('')

// Rows in the DOM, as the first cell's text.
const order = (root: HTMLElement) => Array.from(root.querySelectorAll('tbody tr')).map((tr) => tr.children[0].textContent)
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

export default {
    title: 'Components/Data display/DataTable',
    component: DataTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'Semantic tabular data: a real `<table>` with a `<thead>` built from `columns`, in an edge-fading horizontal scroller. The caller writes the `<tr><td>` rows in the default slot; cells take `data-table__numeric` (right-aligned, tabular figures) and `data-table__actions` (right-aligned, shrink-wrapped). Use it instead of a hand-written `<table>`; for rows made of free-form components use RowList, for a grid-layout board use DataGrid.',
                    'A column with `sortable` gets a header button and `aria-sort`; clicking sorts the rows already on the page (ascending, descending, then the original order). Cells sort by their `data-sort-<column key>` attribute, else their text; `numeric` columns compare as numbers. Server-side paging and sorting stay htmx (HtmxPager or `hx-get`): DataTable never fetches.',
                    '`borders`: `rows` (default) boxes each cell, `grid` joins the lines, `none` drops them. `density="dense"` tightens the padding, `striped` shades alternate rows, `sticky_header` keeps the header in view while the body scrolls. With `is_empty` and an `empty_title` the slot is replaced by one full-width EmptyState row.',
                    'Rows may start with `<th scope="row">`; a `footer` slot becomes the `<tfoot>`; `bodies` is for callers that write several `<tbody>` groups themselves. `variant="report"` is the report-board look (bar cells take `data-table__bar` and a `--bar` fill width); `variant="cards"` stacks rows into labelled cards below 48rem; `visually_hidden` renders a screen-reader-only data table behind a chart.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        columns: { control: 'object', description: 'The header: `key`, `label`, and optional `numeric`, `sortable`, `width` (token or %), `hidden_label`, `hide_below` (a width such as `48rem`: the column hides below it) and `class` (on the header cell).' },
        caption: { control: 'text', description: 'Visually hidden `<caption>`; also names the scroll region.' },
        density: radio_control(['default', 'dense'] as const, 'Cell padding.'),
        borders: radio_control(['rows', 'grid', 'none'] as const, 'Cell lines: `rows` boxes each cell (default), `grid` joins them, `none` drops them.'),
        striped: { control: 'boolean', description: 'Shade alternate rows.' },
        sticky_header: { control: 'boolean', description: 'Keep the header in view; the table scrolls inside a capped height (`--data-table-max-height`).' },
        empty_title: { control: 'text', description: 'Message shown in one full-width row when `is_empty` is set.' },
        is_empty: { control: 'boolean', description: 'Replace the slotted rows with the empty row.' },
        variant: radio_control(['default', 'report', 'cards'] as const, '`report`: editorial hairline rows with muted uppercase headers; `cards`: rows stack as cards below 48rem (cells carry `data-label`).'),
        cards: { control: 'boolean', description: 'Stacked cards below 48rem on top of any variant (the report look keeps its hairlines).' },
        bodies: { control: 'boolean', description: 'The caller writes its own `<tbody>` elements; the slot is not wrapped (no sorting, no empty row).' },
        caption_visible: { control: 'boolean', description: 'Show the caption instead of hiding it visually.' },
        visually_hidden: { control: 'boolean', description: 'Render a screen-reader-only table (chart data); no scroller, nothing painted.' },
    },
    args: {
        columns,
        caption: 'Recent fleets',
        density: 'default',
        borders: 'rows',
        striped: false,
        sticky_header: false,
        is_empty: false,
        slots: { default: rows },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const table = canvas.getByRole('table', { name: 'Recent fleets' })
        await expect(table).toHaveClass('data-table', 'data-table--default', 'data-table--rows')
        await expect(within(table).getAllByRole('columnheader')).toHaveLength(5)
        await expect(within(table).getAllByRole('row')).toHaveLength(5)
        await expect(canvas.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument()
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeTruthy()
    },
}

export const Sortable = {
    name: 'Sorting (text, numeric and data-sort)',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(order(canvasElement)).toEqual(['Fleet 94', 'Fleet 93', 'Fleet 92', 'Fleet 91'])

        // Numeric column: ascending, then descending, then back to the original order.
        const pilots = canvas.getByRole('button', { name: 'Pilots' })
        await userEvent.click(pilots)
        await waitFor(() => expect(order(canvasElement)).toEqual(['Fleet 92', 'Fleet 93', 'Fleet 94', 'Fleet 91']))
        await userEvent.click(pilots)
        await waitFor(() => expect(order(canvasElement)).toEqual(['Fleet 91', 'Fleet 94', 'Fleet 93', 'Fleet 92']))
        await userEvent.click(pilots)
        await waitFor(() => expect(order(canvasElement)).toEqual(['Fleet 94', 'Fleet 93', 'Fleet 92', 'Fleet 91']))

        // Text column.
        await userEvent.click(canvas.getByRole('button', { name: 'Hull' }))
        await waitFor(() =>
            expect(order(canvasElement)).toEqual(['Fleet 94', 'Fleet 92', 'Fleet 91', 'Fleet 93']))

        // data-sort-isk beats the formatted text (commas).
        await userEvent.click(canvas.getByRole('button', { name: /SRP paid/ }))
        await waitFor(() => expect(order(canvasElement)).toEqual(['Fleet 92', 'Fleet 93', 'Fleet 94', 'Fleet 91']))
    },
}

export const AriaSort = {
    name: 'aria-sort follows the sorted column',
    // happy-dom reports stale attributes for Alpine-rebound elements; check them in a real browser.
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const header = (name: string | RegExp) => canvas.getByRole('columnheader', { name })
        await expect(header('Pilots')).toHaveAttribute('aria-sort', 'none')
        await expect(header('Actions')).not.toHaveAttribute('aria-sort')
        await userEvent.click(canvas.getByRole('button', { name: 'Pilots' }))
        await waitFor(() => expect(header('Pilots')).toHaveAttribute('aria-sort', 'ascending'))
        await userEvent.click(canvas.getByRole('button', { name: 'Pilots' }))
        await waitFor(() => expect(header('Pilots')).toHaveAttribute('aria-sort', 'descending'))
        await userEvent.click(canvas.getByRole('button', { name: 'Hull' }))
        await waitFor(() => expect(header('Pilots')).toHaveAttribute('aria-sort', 'none'))
    },
}

export const SortableHeaders = {
    name: 'Only sortable columns are buttons',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('button')).toHaveLength(4)
        const actions = canvas.getByRole('columnheader', { name: 'Actions' })
        await expect(within(actions).queryByRole('button')).toBeNull()
        await expect(attr(canvas.getByRole('columnheader', { name: 'Fleet' }), 'aria-sort')).toBe('none')
        await expect(within(actions).getByText('Actions')).toHaveClass('visually-hidden')
    },
}

export const Empty = {
    args: { is_empty: true, empty_title: 'No fleets in this period', slots: { default: rows } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No fleets in this period')).toBeVisible()
        await expect(canvas.queryByText('Fleet 94')).toBeNull()
        const cell = canvasElement.querySelector('tr[data-table-static] td') as HTMLElement
        await expect(cell).toHaveAttribute('colspan', '5')
        // The empty row is not a sortable data row.
        await userEvent.click(canvas.getByRole('button', { name: 'Pilots' }))
        await expect(canvas.getByText('No fleets in this period')).toBeVisible()
    },
}

export const Dense = {
    args: { density: 'dense', borders: 'grid', striped: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const table = within(canvasElement).getByRole('table')
        await expect(table).toHaveClass('data-table--dense', 'data-table--grid', 'data-table--striped')
        await expect(within(table).getAllByRole('row')).toHaveLength(5)
    },
}

export const StickyHeader = {
    name: 'Sticky header (many rows)',
    args: {
        sticky_header: true,
        slots: {
            default: Array.from({ length: 30 }, (_, i) => row([`Fleet ${100 - i}`, 'Rifter', 10 + i, 100000000 * (i + 1)])).join(''),
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.data-table-wrap--sticky')).toBeTruthy()
        await expect(within(canvasElement).getAllByRole('row')).toHaveLength(31)
        await expect(within(canvasElement).getByRole('columnheader', { name: 'Fleet' })).toBeInTheDocument()
    },
}

export const NoBorders = {
    name: 'No borders, no sorting',
    args: {
        borders: 'none',
        columns: columns.map((column) => ({ ...column, sortable: false })),
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('table')).toHaveClass('data-table--none')
        await expect(canvas.queryAllByRole('button')).toHaveLength(0)
    },
}

const row_header_rows = fleets
    .map(([fleet, hull, pilots]) => `<tr><th scope="row">${fleet}</th><td>${hull}</td><td class="data-table__numeric">${pilots}</td></tr>`)
    .join('')

export const RowHeaders = {
    name: 'Row headers and a footer',
    args: {
        columns: [
            { key: 'fleet', label: 'Fleet' },
            { key: 'hull', label: 'Hull' },
            { key: 'pilots', label: 'Pilots', numeric: true },
        ],
        slots: {
            default: row_header_rows,
            footer: '<tr><th scope="row">Total</th><td></td><td class="data-table__numeric">115</td></tr>',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('rowheader', { name: 'Fleet 94' })).toBeInTheDocument()
        await expect(canvasElement.querySelector('tfoot')).toBeTruthy()
        await expect(canvasElement.querySelectorAll('tbody tr')).toHaveLength(4)
        await expect(canvas.getByRole('rowheader', { name: 'Total' })).toBeInTheDocument()
    },
}

export const Bodies = {
    name: 'Own row groups (bodies)',
    args: {
        bodies: true,
        columns: columns.slice(0, 3).map((column) => ({ ...column, sortable: false })),
        slots: {
            default: `<tbody>${fleets.slice(0, 2).map(row).join('')}</tbody><tbody>${fleets.slice(2).map(row).join('')}</tbody>`,
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('tbody')).toHaveLength(2)
        await expect(canvasElement.querySelector('tbody tbody')).toBeNull()
        await expect(within(canvasElement).queryAllByRole('button')).toHaveLength(0)
    },
}

export const HideBelow = {
    name: 'Narrow-hidden column',
    args: {
        columns: [
            { key: 'fleet', label: 'Fleet' },
            { key: 'hull', label: 'Hull', hide_below: '48rem' },
            { key: 'pilots', label: 'Pilots', numeric: true },
            { key: 'isk', label: 'ISK', numeric: true },
            { key: 'actions', label: 'Open fleet', hidden_label: true },
        ],
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = canvasElement.querySelector('style') as HTMLStyleElement
        await expect(style.textContent).toContain('max-width: 48rem')
        await expect(style.textContent).toContain('nth-child(2)')
        await expect(canvasElement.querySelector('table')?.className).toMatch(/data-table-h\d+/)
    },
}

export const Report = {
    name: 'Report variant with a bar column',
    args: {
        variant: 'report',
        columns: [
            { key: 'hull', label: 'Hull' },
            { key: 'bar', label: 'Pilots', class: 'data-table__bar' },
            { key: 'isk', label: 'ISK', numeric: true },
        ],
        slots: {
            default: fleets
                .map(([, hull, pilots, isk]) => `<tr><td>${hull}</td><td class="data-table__bar" style="--bar: ${pilots}%"><b>${pilots}</b></td><td class="data-table__numeric">${isk.toLocaleString('en-US')}</td></tr>`)
                .join(''),
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('table')).toHaveClass('data-table--report')
        await expect(canvasElement.querySelectorAll('td.data-table__bar')).toHaveLength(4)
        await expect(canvasElement.querySelector('th.data-table__bar')).toBeTruthy()
    },
}

export const Cards = {
    name: 'Cards below 48rem',
    args: {
        variant: 'cards',
        columns: columns.slice(0, 4),
        slots: {
            default: fleets
                .map(([fleet, hull, pilots, isk]) => `<tr><td class="data-table__card-title">${fleet}</td><td data-label="Hull">${hull}</td><td data-label="Pilots" class="data-table__numeric">${pilots}</td><td data-label="ISK" class="data-table__numeric">${isk.toLocaleString('en-US')}</td></tr>`)
                .join(''),
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('table')).toHaveClass('data-table--cards')
        await expect(canvasElement.querySelectorAll('td[data-label]')).toHaveLength(12)
    },
}

export const ScreenReaderOnly = {
    name: 'Screen-reader-only table',
    args: { visually_hidden: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const table = within(canvasElement).getByRole('table', { name: 'Recent fleets' })
        await expect(table.parentElement).toHaveClass('visually-hidden')
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeNull()
        await expect(within(table).getAllByRole('row')).toHaveLength(5)
    },
}

export const VisibleCaption = {
    args: { caption_visible: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const caption = canvasElement.querySelector('caption') as HTMLElement
        await expect(caption).toHaveClass('data-table__caption')
        await expect(caption).not.toHaveClass('visually-hidden')
    },
}
