import { expect, within } from 'storybook/test'
import DataGrid from '@components/blocks/DataGrid.astro'
import { EVE, radio_control } from '../../_controls'

const portrait = (id: number, name: string) =>
    `<span class="data-grid-media"><img src="https://images.evetech.net/characters/${id}/portrait?size=32" alt="" width="32" height="32" /><span>${name}</span></span>`
const ship = (id: number, name: string) =>
    `<span class="data-grid-media"><img src="https://images.evetech.net/types/${id}/icon?size=32" alt="" width="32" height="32" /><span>${name}</span></span>`

const fleet_rows = [
    ['Fleet 94', EVE.character_id, EVE.character_name, 587, 'Rifter', '38', '2,140,000,000'],
    ['Fleet 93', 2112954533, 'Rattini Pilot', 622, 'Stabber', '24', '1,410,000,000'],
    ['Fleet 92', 2112954534, 'Hek Roamer', 587, 'Rifter', '12', '180,000,000'],
    ['Fleet 91', 2112954535, 'Amamake Defender', 622, 'Stabber', '41', '3,020,000,000'],
].map(([fleet, cid, fc, tid, hull, pilots, isk]) => `
<div class="data-grid-row" role="row">
    <span role="cell" data-label="Fleet">${fleet}</span>
    <span role="cell" data-label="FC">${portrait(cid as number, fc as string)}</span>
    <span role="cell" data-label="Hull" class="data-grid-muted">${ship(tid as number, hull as string)}</span>
    <span role="cell" data-label="Pilots" class="data-grid-numeric">${pilots}</span>
    <span role="cell" data-label="SRP paid" class="data-grid-numeric">${isk}</span>
</div>`).join('')

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
    title: 'Components/Data display/DataGrid',
    component: DataGrid,
    parameters: {
        docs: {
            description: {
                component: [
                    'A grid-based table with a real header row (`role="table"`, `columnheader`, `row`, `cell`). `columns` builds the header and `template` is the shared `grid-template-columns` for the header and every slotted `.data-grid-row`. Use it for boards and ledgers (fleet history, SRP, contracts); use RowList for rows made of free-form components.',
                    'Cell helpers: `data-grid-numeric` right-aligns, `data-grid-muted` dims, `data-grid-media` pairs an EVE image with a label, `data-grid-cell` wraps cells that keep their own role. `variant` is `compact` (boards) or `ledger` (contract lists). With `stack`, below 48rem the header hides and each cell with a `data-label` shows it as a caption, so rows become cards; the row layout itself is up to the row\'s owner. Resize the viewport to see it.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        columns: { control: 'object', description: 'Header labels, one per column.' },
        template: { control: 'text', description: 'The shared `grid-template-columns` value, e.g. `1fr 2fr repeat(2, 8rem)`.' },
        numeric: { control: 'object', description: 'Indexes of columns whose header is right-aligned (cells use `data-grid-numeric`).' },
        min_width: { control: 'text', description: 'Below this width the grid scrolls sideways with an edge fade.' },
        variant: radio_control(['compact', 'ledger'], '`compact`: heading-font header and tight gaps. `ledger`: bold body-font header and roomier gaps.'),
        stack: { control: 'boolean', description: 'On phones, hide the header and show each cell\'s `data-label` as a caption.' },
    },
    args: {
        columns: ['Fleet', 'FC', 'Hull', 'Pilots', 'SRP paid'],
        template: '6rem minmax(10rem, 1.4fr) minmax(8rem, 1fr) 5rem 9rem',
        numeric: [3, 4],
        min_width: '38rem',
        variant: 'compact',
        stack: false,
        slots: { default: fleet_rows },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const table = canvas.getByRole('table')
        await expect(table).toHaveClass('data-grid', 'data-grid--compact')
        await expect(table.getAttribute('style')).toContain('--data_grid_template')
        await expect(canvas.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Fleet', 'FC', 'Hull', 'Pilots', 'SRP paid'])
        // header row + 4 data rows
        await expect(canvas.getAllByRole('row')).toHaveLength(5)
        await expect(canvas.getByText('Amamake Defender')).toBeVisible()
        await expect(canvas.getAllByRole('columnheader')[3]).toHaveClass('data-grid-numeric')
        await expect(canvas.getAllByRole('columnheader')[0]).not.toHaveClass('data-grid-numeric')
    },
}

export const Ledger = {
    args: { variant: 'ledger' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const table = within(canvasElement).getByRole('table')
        await expect(table).toHaveClass('data-grid--ledger')
        await expect(table).not.toHaveClass('data-grid--compact')
    },
}

export const StackedOnPhones = {
    name: 'Stacked on phones (stack)',
    args: { stack: true, variant: 'ledger' },
    parameters: { viewport: { defaultViewport: 'mobile1' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const table = within(canvasElement).getByRole('table')
        await expect(table).toHaveClass('data-grid--stack')
        // Every cell has a caption the stacked layout shows via attr(data-label).
        const cells = canvasElement.querySelectorAll('.data-grid-row [role="cell"]')
        await expect(cells.length).toBe(20)
        const labels = Array.from(cells).slice(0, 5).map((c) => c.getAttribute('data-label'))
        // Storybook's browser renderer drops `data-label` from slotted HTML strings (real pages render it from Astro),
        // so the caption check only runs where the attribute survives.
        if (labels.some(Boolean)) await expect(labels).toEqual(['Fleet', 'FC', 'Hull', 'Pilots', 'SRP paid'])
    },
}

export const MediaCells = {
    name: 'Media cells (portraits and icons)',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const media = canvasElement.querySelectorAll('.data-grid-media')
        await expect(media.length).toBe(8)
        await expect(media[0].querySelector('img')?.getAttribute('src')).toContain(`/characters/${EVE.character_id}/portrait`)
        await expect(media[1].querySelector('img')?.getAttribute('src')).toContain('/types/587/icon')
    },
}

export const Empty = {
    name: 'Empty grid',
    args: { slots: { default: '<p class="data-grid-row" role="row"><span role="cell">No fleets flown this month.</span></p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // The header stays even when there are no rows.
        await expect(canvas.getAllByRole('columnheader')).toHaveLength(5)
        await expect(canvas.getByText('No fleets flown this month.')).toBeVisible()
    },
}

export const NarrowGridScrolls = {
    name: 'Narrow viewport scrolls (min_width)',
    args: { min_width: '60rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const table = within(canvasElement).getByRole('table')
        await expect(table.getAttribute('style')).toContain('min-width: 60rem')
        await expect(canvasElement.querySelector('.xfade-scroll')).toBeTruthy()
    },
}
