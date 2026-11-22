import { expect, within } from 'storybook/test'
import Chart from '@components/blocks/Chart.astro'
import { select_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const TONES = ['fleet-red', 'green', 'alliance-blue', 'militia-purple', 'fleet-yellow', 'highlight', 'faded'] as const

const WEEKS = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6']

const canvas_of = (canvasElement: HTMLElement) => canvasElement.querySelector('canvas') as HTMLCanvasElement
const spec_of = (canvasElement: HTMLElement) => JSON.parse(canvas_of(canvasElement).dataset.chart ?? 'null')

export default {
    title: 'Components/Data display/Chart',
    component: Chart,
    parameters: {
        docs: {
            description: {
                component: [
                    'A Chart.js chart in the site\'s colours. Pass `type` (`line`, `bar`, `doughnut`, `pie`, `radar`), `labels` and `datasets`; each dataset names a `tone`, a colour token (`fleet-red`, `green`, `alliance-blue`, `militia-purple`, `fleet-yellow`, `highlight`, `faded`) that is resolved from CSS at runtime, so color-blind mode applies. The grid, ticks and tooltip use `--faded`, `--border-color` and `--component-background`. `options` is deep-merged over the defaults; `legend` defaults to on for several datasets, doughnut and pie.',
                    'Doughnut and pie datasets take `tones`, one per slice, and cycle the palette when they name none. The component renders a `<canvas role="img" aria-label>` with the spec as JSON in `data-chart`; a script charts every such canvas with the global `Chart` that FooterScripts loads, once, also after an htmx swap, and destroys the instance when the canvas is replaced. With nothing to plot it renders an `EmptyState` instead of an empty canvas.',
                    'Chart.js loads from the CDN, so in vitest the stories assert the markup and the `data-chart` JSON; Storybook draws the real charts.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        type: select_control(['line', 'bar', 'doughnut', 'pie', 'radar'], 'Chart kind.'),
        labels: { control: 'object', description: 'One label per data point.' },
        datasets: { control: 'object', description: 'Series: `{ label, data, tone?, tones?, fill?, type? }`. Extra keys pass to Chart.js.' },
        options: { control: 'object', description: 'Chart.js options, deep-merged over the defaults.' },
        height: { control: 'text', description: 'CSS height of the chart area (a token expression by default).' },
        aria_label: { control: 'text', description: 'What the chart shows, for screen readers.' },
        legend: { control: 'boolean', description: 'Show the legend. Defaults to on for several datasets, doughnut and pie.' },
        empty_title: { control: 'text', description: 'Replaces "No data to chart" when there is nothing to plot.' },
    },
    args: {
        type: 'line',
        labels: WEEKS,
        datasets: [{ label: 'Kills', data: [12, 19, 15, 28, 24, 33], tone: 'fleet-red' }],
        aria_label: 'Kills per week',
    },
}

export const Line = {
    args: {
        datasets: [
            { label: 'Kills', data: [12, 19, 15, 28, 24, 33], tone: 'fleet-red' },
            { label: 'Losses', data: [9, 11, 14, 10, 18, 12], tone: 'alliance-blue', fill: true },
        ],
        aria_label: 'Kills and losses per week',
    },
    play: async ({ canvasElement }: Ctx) => {
        const chart = within(canvasElement).getByRole('img', { name: 'Kills and losses per week' })
        await expect(chart.tagName).toBe('CANVAS')
        const spec = spec_of(canvasElement)
        await expect(spec.type).toBe('line')
        await expect(spec.labels).toEqual(WEEKS)
        await expect(spec.datasets.map((dataset: { label: string }) => dataset.label)).toEqual(['Kills', 'Losses'])
        await expect(spec.datasets[0].tone).toBe('fleet-red')
        await expect(spec.datasets[1].fill).toBe(true)
    },
}

export const Bar = {
    args: {
        type: 'bar',
        labels: ['Rifter', 'Wolf', 'Jaguar', 'Slasher'],
        datasets: [{ label: 'Fits sold', data: [42, 18, 25, 9], tone: 'green' }],
        aria_label: 'Fits sold by hull',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img', { name: 'Fits sold by hull' })).toBeVisible()
        const spec = spec_of(canvasElement)
        await expect(spec.type).toBe('bar')
        await expect(spec.datasets[0].data).toEqual([42, 18, 25, 9])
        await expect(spec.datasets[0].tone).toBe('green')
        // One dataset, so no legend unless asked for.
        await expect(spec.legend).toBeUndefined()
    },
}

export const Doughnut = {
    args: {
        type: 'doughnut',
        labels: ['Heimatar', 'Metropolis', 'Molden Heath'],
        datasets: [{ label: 'Systems held', data: [14, 9, 6], tones: ['fleet-red', 'alliance-blue', 'fleet-yellow'] }],
        aria_label: 'Systems held by region',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img', { name: 'Systems held by region' })).toBeVisible()
        const spec = spec_of(canvasElement)
        await expect(spec.type).toBe('doughnut')
        await expect(spec.datasets[0].tones).toEqual(['fleet-red', 'alliance-blue', 'fleet-yellow'])
    },
}

export const Pie = {
    args: {
        type: 'pie',
        labels: ['Ships', 'Modules', 'Charges'],
        datasets: [{ label: 'Share', data: [55, 30, 15] }],
        aria_label: 'Market share by category',
        legend: false,
    },
    play: async ({ canvasElement }: Ctx) => {
        const spec = spec_of(canvasElement)
        await expect(spec.type).toBe('pie')
        await expect(spec.legend).toBe(false)
        // No tones named: the palette cycles.
        await expect(spec.datasets[0].tones).toBeUndefined()
    },
}

export const Radar = {
    args: {
        type: 'radar',
        labels: ['Tackle', 'DPS', 'Logistics', 'Scouting', 'Command'],
        datasets: [{ label: 'Readiness', data: [8, 6, 4, 7, 5], tone: 'militia-purple' }],
        aria_label: 'Readiness by role',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(spec_of(canvasElement).type).toBe('radar')
    },
}

export const OptionsMerge = {
    name: 'Options and height',
    args: {
        options: { scales: { y: { max: 50 } } },
        height: 'var(--space-3xl)',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(spec_of(canvasElement).options).toEqual({ scales: { y: { max: 50 } } })
        await expect(canvasElement.querySelector('.chart')?.getAttribute('style')).toContain('--chart-height: var(--space-3xl)')
    },
}

export const MissingData = {
    name: 'Missing data',
    args: {
        labels: [],
        datasets: [{ label: 'Kills', data: [], tone: 'fleet-red' }],
        empty_title: 'No kills recorded yet',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No kills recorded yet')).toBeVisible()
        await expect(canvasElement.querySelector('canvas')).toBeNull()
    },
}

export const OnlyNulls = {
    name: 'Missing data: every point null',
    args: {
        datasets: [{ label: 'Kills', data: [null, null, null, null, null, null], tone: 'fleet-red' }],
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No data to chart')).toBeVisible()
        await expect(canvasElement.querySelector('canvas')).toBeNull()
    },
}

export const Tones = {
    args: {
        type: 'bar',
        labels: [...TONES],
        datasets: [{ label: 'Every tone', data: [7, 6, 5, 4, 3, 2, 1], tones: [...TONES] }],
        aria_label: 'One bar per tone',
    },
    play: async ({ canvasElement }: Ctx) => {
        await expect(spec_of(canvasElement).datasets[0].tones).toHaveLength(7)
    },
}

export const Gradient = {
    name: 'Gradient, suffix and ringed points',
    args: {
        datasets: [
            { label: 'ISK destroyed', data: [4.2, 6.8, 5.1, 9.4, 7.7, 11.3], tone: 'green', gradient: 40, ring: true, suffix: ' B', tension: 0 },
        ],
        tick_suffix: ' B',
        aria_label: 'ISK destroyed per week, in billions',
    },
    play: async ({ canvasElement }: Ctx) => {
        const spec = spec_of(canvasElement)
        await expect(spec.tick_suffix).toBe(' B')
        await expect(spec.datasets[0].gradient).toBe(40)
        await expect(spec.datasets[0].ring).toBe(true)
        await expect(spec.datasets[0].suffix).toBe(' B')
    },
}

export const Plugins = {
    name: 'Droplines, band and markers',
    args: {
        datasets: [{ label: 'Damage', data: [3, 0, 7, 4, 9, 2], tone: 'fleet-red', fill: false, borderWidth: 0, pointRadius: 2 }],
        options: { layout: { padding: { bottom: 50 } } },
        plugins: [
            { id: 'stems' },
            { id: 'band', from: 2, to: 3 },
            { id: 'beats', beats: [{ index: 4, label: 'Capital fight', row: 0, anchor: 'middle', dx: 0 }] },
        ],
        aria_label: 'Damage per tick with the capital fight marked',
    },
    play: async ({ canvasElement }: Ctx) => {
        const spec = spec_of(canvasElement)
        await expect(spec.plugins.map((plugin: { id: string }) => plugin.id)).toEqual(['stems', 'band', 'beats'])
        await expect(spec.plugins[2].beats[0].label).toBe('Capital fight')
    },
}
