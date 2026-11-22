import { describe, expect, test, vi } from 'vitest'
import { bind_charts, build_config, deep_merge, has_plottable_data, mount_chart, type ChartSpec, type ChartWindow } from '@helpers/chart'

const TOKENS: Record<string, string> = {
    '--fleet-red': 'rgb(1, 2, 3)',
    '--alliance-blue': 'rgb(4, 5, 6)',
    '--green': 'rgb(7, 8, 9)',
    '--faded': 'rgba(255, 255, 255, 0.5)',
    '--border-color': 'rgba(255, 255, 255, 0.1)',
    '--component-background': 'rgb(25, 25, 25)',
    '--foreground': 'rgb(241, 217, 160)',
    '--highlight': 'rgb(255, 255, 255)',
}
const read = (name: string) => TOKENS[name] ?? ''

const spec = (patch: Partial<ChartSpec> = {}): ChartSpec => ({
    type: 'line',
    labels: ['a', 'b'],
    datasets: [{ label: 'Kills', data: [1, 2], tone: 'fleet-red' }],
    ...patch,
})

describe('build_config', () => {
    test('resolves a tone from its token, never a literal', () => {
        const config = build_config(spec(), read)
        expect(config.data.datasets[0].borderColor).toBe('rgb(1, 2, 3)')
        expect(config.data.datasets[0].fill).toBe(false)
    })

    test('theme comes from the tokens', () => {
        const options = build_config(spec(), read).options
        expect(options.scales.x.ticks.color).toBe(TOKENS['--faded'])
        expect(options.scales.y.grid.color).toBe(TOKENS['--border-color'])
        expect(options.plugins.tooltip.backgroundColor).toBe(TOKENS['--component-background'])
    })

    test('options are deep-merged over the defaults', () => {
        const options = build_config(spec({ options: { scales: { y: { max: 50 } } } }), read).options
        expect(options.scales.y.max).toBe(50)
        expect(options.scales.y.beginAtZero).toBe(true)
        expect(options.scales.x.ticks.color).toBe(TOKENS['--faded'])
    })

    test('the legend follows the dataset count unless set', () => {
        expect(build_config(spec(), read).options.plugins.legend.display).toBe(false)
        expect(build_config(spec({ datasets: [{ label: 'a', data: [1] }, { label: 'b', data: [2] }] }), read).options.plugins.legend.display).toBe(true)
        expect(build_config(spec({ legend: true }), read).options.plugins.legend.display).toBe(true)
    })

    test('doughnut slices take per-point tones', () => {
        const config = build_config(spec({ type: 'doughnut', datasets: [{ label: 's', data: [1, 2], tones: ['green', 'alliance-blue'] }] }), read)
        expect(config.data.datasets[0].borderColor).toEqual(['rgb(7, 8, 9)', 'rgb(4, 5, 6)'])
        expect(config.options.scales).toBeUndefined()
    })

    test('reduced motion turns animation off', () => {
        expect(build_config(spec(), read, true).options.animation).toBe(false)
    })
})

test('deep_merge replaces arrays and keeps siblings', () => {
    expect(deep_merge({ a: { b: 1, c: [1] }, d: 1 }, { a: { c: [2] } })).toEqual({ a: { b: 1, c: [2] }, d: 1 })
})

test('has_plottable_data needs a number', () => {
    expect(has_plottable_data(spec())).toBe(true)
    expect(has_plottable_data(spec({ labels: [] }))).toBe(false)
    expect(has_plottable_data(spec({ datasets: [{ label: 'a', data: [null, null] }] }))).toBe(false)
})

describe('lifecycle', () => {
    function setup() {
        const created: { canvas: HTMLCanvasElement; destroyed: boolean }[] = []
        class FakeChart {
            static owned = new Map<HTMLCanvasElement, FakeChart>()
            static getChart = (canvas: HTMLCanvasElement) => FakeChart.owned.get(canvas)
            record: { canvas: HTMLCanvasElement; destroyed: boolean }
            constructor(canvas: HTMLCanvasElement) {
                this.record = { canvas, destroyed: false }
                created.push(this.record)
                FakeChart.owned.set(canvas, this)
            }
            destroy() { this.record.destroyed = true; FakeChart.owned.delete(this.record.canvas) }
        }
        const win = window as unknown as ChartWindow
        win.Chart = FakeChart as unknown as ChartWindow['Chart']
        win.__minmatar_charts_bound = false
        document.body.innerHTML = ''
        return { win, created }
    }

    const add_canvas = (host: HTMLElement) => {
        const canvas = document.createElement('canvas')
        canvas.dataset.chart = JSON.stringify(spec())
        host.append(canvas)
        return canvas
    }

    test('mount_chart charts a canvas once', () => {
        const { win, created } = setup()
        const canvas = add_canvas(document.body)
        expect(mount_chart(win, canvas)).toBe(true)
        expect(mount_chart(win, canvas)).toBe(true)
        expect(created).toHaveLength(1)
    })

    test('a canvas swapped in is charted and the replaced one is destroyed', async () => {
        const { win, created } = setup()
        const host = document.createElement('div')
        document.body.append(host)
        const first = add_canvas(host)
        bind_charts(win)
        expect(created.map((record) => record.canvas)).toEqual([first])

        host.replaceChildren()
        const second = add_canvas(host)
        await vi.waitFor(() => expect(created).toHaveLength(2))
        expect(created[0].destroyed).toBe(true)
        expect(created[1].canvas).toBe(second)
        expect(created[1].destroyed).toBe(false)
    })

    test('a missing global Chart charts nothing and does not throw', () => {
        const { win } = setup()
        win.Chart = undefined
        expect(mount_chart(win, add_canvas(document.body))).toBe(false)
    })
})
