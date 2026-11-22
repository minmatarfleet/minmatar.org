/**
 * Chart.js glue for blocks/Chart.astro: the config a chart spec becomes (tones
 * read from CSS tokens at runtime, theme from the site's colours) and the
 * mount/destroy lifecycle that follows the DOM, so a canvas an htmx swap, a
 * ClientRouter navigation or an Alpine template adds is charted once, and its
 * instance is destroyed when the canvas goes.
 *
 * The global `Chart` comes from FooterScripts; nothing here imports Chart.js.
 */

export type ChartTone = 'fleet-red' | 'green' | 'alliance-blue' | 'militia-purple' | 'fleet-yellow' | 'highlight' | 'faded'

export interface ChartDataset {
    label:      string;
    data:       (number | null)[];
    tone?:      ChartTone;
    /** One tone per point, for doughnut, pie and radial charts. */
    tones?:     ChartTone[];
    fill?:      boolean;
    type?:      string;
    /** Appended to the value in the tooltip (`' B'` reads `Ratting: 4.2 B`). */
    suffix?:    string;
    /** Fill a line under it with its tone fading to nothing; the number is the opacity at the top, in percent. */
    gradient?:  number;
    /** Ring the line's points with the panel colour, so they stand off the line. */
    ring?:      boolean;
    [key: string]: any;
}

export type ChartKind = 'line' | 'bar' | 'doughnut' | 'pie' | 'radar'

/** A label under the x axis, joined to a category by a dotted stem. `row` stacks labels that would collide. */
export interface ChartBeat {
    index:      number;
    label:      string;
    row?:       number;
    anchor?:    'start' | 'middle' | 'end';
    dx?:        number;
}

/** Drawing the chart itself does not cover. Each is built in `build_plugin`. */
export type ChartPluginSpec =
    /** A dropline from every point down to zero, in its dataset's tone. */
    | { id: 'stems' }
    /** Shades the categories `from` to `to` (inclusive) with the panel colour. */
    | { id: 'band'; from: number; to: number }
    /** Labelled markers under the x axis; give the chart bottom padding for them. */
    | { id: 'beats'; beats: ChartBeat[] }

export interface ChartSpec {
    type:       ChartKind;
    labels:     (string | number)[];
    datasets:   ChartDataset[];
    options?:   Record<string, any>;
    legend?:    boolean;
    /** Appended to the numbers on the y axis (`' B'`). */
    tick_suffix?: string;
    plugins?:   ChartPluginSpec[];
}

/** Order slices take when a doughnut or pie dataset names no tones. */
export const TONE_CYCLE: ChartTone[] = ['alliance-blue', 'fleet-red', 'green', 'fleet-yellow', 'militia-purple', 'highlight', 'faded']

/** Reads a CSS custom property (`--fleet-red`) as its value. */
export type TokenReader = (name: string) => string

export const css_token_reader = (win: Window = window): TokenReader => {
    const style = win.getComputedStyle(win.document.documentElement)
    return (name) => style.getPropertyValue(name).trim()
}

export const resolve_tone = (tone: ChartTone, read: TokenReader) => read(`--${tone}`)

/** `color` at `percent` opacity; the canvas resolves color-mix like any CSS colour. */
export const with_alpha = (color: string, percent: number) => `color-mix(in srgb, ${color} ${percent}%, transparent)`

const is_plain_object = (value: unknown): value is Record<string, any> =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

/** Deep-merge `override` over `base`; arrays and scalars in `override` replace. */
export function deep_merge<T extends Record<string, any>>(base: T, override?: Record<string, any>): T {
    if (!override) return base
    const result: Record<string, any> = { ...base }
    for (const [key, value] of Object.entries(override))
        result[key] = is_plain_object(value) && is_plain_object(result[key]) ? deep_merge(result[key], value) : value
    return result as T
}

/** True when there is at least one number to plot. */
export const has_plottable_data = (spec: Pick<ChartSpec, 'labels' | 'datasets'>) =>
    spec.labels.length > 0 && spec.datasets.some((dataset) => dataset.data.some((point) => typeof point === 'number' && Number.isFinite(point)))

const is_radial = (type: ChartKind) => type === 'doughnut' || type === 'pie'

function style_dataset(dataset: ChartDataset, index: number, spec: ChartSpec, read: TokenReader) {
    const { tone, tones, fill, gradient, ring, ...rest } = dataset
    const type = rest.type as ChartKind | undefined ?? spec.type

    if (is_radial(type)) {
        const slice_tones = tones ?? dataset.data.map((_, point) => tone ?? TONE_CYCLE[point % TONE_CYCLE.length])
        return {
            ...rest,
            backgroundColor: slice_tones.map((slice) => with_alpha(resolve_tone(slice, read), 70)),
            borderColor: slice_tones.map((slice) => resolve_tone(slice, read)),
            borderWidth: 1,
        }
    }

    const color = resolve_tone(tone ?? TONE_CYCLE[index % TONE_CYCLE.length], read)
    if (type === 'bar')
        return { ...rest, backgroundColor: with_alpha(color, 60), borderColor: color, borderWidth: 1 }

    // line and radar
    const filled = fill ?? (type === 'radar' || gradient !== undefined)
    const surface = read('--component-background')
    const area = gradient !== undefined
        ? (context: { chart: { ctx: CanvasRenderingContext2D; chartArea?: { top: number; bottom: number } } }) => {
            const chart_area = context.chart.chartArea
            if (!chart_area) return 'transparent'
            const fade = context.chart.ctx.createLinearGradient(0, chart_area.top, 0, chart_area.bottom)
            fade.addColorStop(0, with_alpha(color, gradient))
            fade.addColorStop(1, with_alpha(color, 0))
            return fade
        }
        : filled ? with_alpha(color, 20) : color
    return {
        ...rest,
        borderColor: color,
        backgroundColor: area,
        pointBackgroundColor: color,
        pointBorderColor: ring ? surface : color,
        fill: filled,
        tension: rest.tension ?? 0.25,
    }
}

const plot_bounds = (chart: any) => ({ x: chart.scales.x, y: chart.scales.y, area: chart.chartArea })

/** A Chart.js plugin for one of the drawing specs. */
export function build_plugin(spec: ChartPluginSpec, read: TokenReader) {
    if (spec.id === 'stems') return {
        id: 'stems',
        beforeDraw(chart: any) {
            const { x, y } = plot_bounds(chart)
            const ctx = chart.ctx
            ctx.save()
            chart.data.datasets.forEach((dataset: any) => {
                ctx.strokeStyle = with_alpha(String(dataset.borderColor), 25)
                ctx.lineWidth = 1
                dataset.data.forEach((value: number, index: number) => {
                    ctx.beginPath()
                    ctx.moveTo(x.getPixelForValue(index), y.getPixelForValue(value))
                    ctx.lineTo(x.getPixelForValue(index), y.getPixelForValue(0))
                    ctx.stroke()
                })
            })
            ctx.restore()
        },
    }

    if (spec.id === 'band') return {
        id: 'band',
        beforeDraw(chart: any) {
            const { x, area } = plot_bounds(chart)
            const slot = x.getPixelForValue(1) - x.getPixelForValue(0)
            const left = x.getPixelForValue(spec.from) - slot / 2
            const right = x.getPixelForValue(spec.to) + slot / 2
            chart.ctx.save()
            chart.ctx.fillStyle = with_alpha(read('--component-background'), 50)
            chart.ctx.fillRect(left, area.top, right - left, area.bottom - area.top)
            chart.ctx.restore()
        },
    }

    const color = read('--fleet-yellow')
    const family = read('--default-font')
    return {
        id: 'beats',
        afterDraw(chart: any) {
            const { x, area } = plot_bounds(chart)
            const ctx = chart.ctx
            const stem_start = area.bottom + 20
            const label_top = area.bottom + 50
            ctx.save()
            for (const beat of spec.beats) {
                const cx = x.getPixelForValue(beat.index)
                const dx = beat.dx ?? 0
                const label_y = label_top + (beat.row ?? 0) * 20

                ctx.beginPath()
                ctx.moveTo(cx, stem_start)
                ctx.lineTo(cx + dx, label_y - 10)
                ctx.strokeStyle = with_alpha(color, 35)
                ctx.lineWidth = 1
                ctx.setLineDash([2, 3])
                ctx.stroke()
                ctx.setLineDash([])

                ctx.font = `600 10px ${family || 'sans-serif'}`
                ctx.fillStyle = with_alpha(color, 80)
                ctx.textAlign = beat.anchor ?? 'middle'
                ctx.textBaseline = 'middle'
                ctx.fillText(beat.label, cx + dx, label_y)
            }
            ctx.restore()
        },
    }
}

/** The full Chart.js configuration for a spec. */
export function build_config(spec: ChartSpec, read: TokenReader, reduce_motion = false) {
    const faded = read('--faded')
    const border = read('--border-color')
    const surface = read('--component-background')
    const text = read('--foreground')
    const highlight = read('--highlight')
    const radial = is_radial(spec.type)

    const defaults: Record<string, any> = {
        responsive: true,
        maintainAspectRatio: false,
        animation: reduce_motion ? false : undefined,
        font: read('--default-font') ? { family: read('--default-font') } : undefined,
        plugins: {
            legend: {
                display: spec.legend ?? (radial || spec.datasets.length > 1),
                labels: { color: faded },
            },
            tooltip: {
                backgroundColor: surface,
                borderColor: border,
                borderWidth: 1,
                titleColor: highlight,
                bodyColor: text,
                ...(spec.datasets.some((dataset) => dataset.suffix !== undefined) && {
                    callbacks: {
                        label: (context: any) => `${context.dataset.label}: ${context.formattedValue}${context.dataset.suffix ?? ''}`,
                    },
                }),
            },
        },
    }

    if (spec.type === 'line' || spec.type === 'bar') {
        defaults.scales = {
            x: { grid: { color: border }, ticks: { color: faded }, border: { color: border } },
            y: {
                grid: { color: border },
                ticks: { color: faded, ...(spec.tick_suffix && { callback: (value: number | string) => `${value}${spec.tick_suffix}` }) },
                border: { color: border },
                beginAtZero: true,
            },
        }
        // A second value axis (`y1`) in the caller's options looks like the first.
        for (const key of Object.keys(spec.options?.scales ?? {}))
            if (!(key in defaults.scales)) defaults.scales[key] = { grid: { color: border }, ticks: { color: faded }, border: { color: border } }
    } else if (spec.type === 'radar') {
        defaults.scales = {
            r: { grid: { color: border }, angleLines: { color: border }, pointLabels: { color: faded }, ticks: { color: faded, backdropColor: 'transparent' } },
        }
    }

    return {
        type: spec.type,
        data: {
            labels: spec.labels,
            datasets: spec.datasets.map((dataset, index) => style_dataset(dataset, index, spec, read)),
        },
        options: deep_merge(defaults, spec.options),
        plugins: (spec.plugins ?? []).map((plugin) => build_plugin(plugin, read)),
    }
}

interface ChartInstance { destroy: () => void }
interface ChartGlobal {
    new (canvas: HTMLCanvasElement, config: unknown): ChartInstance;
    getChart?: (canvas: HTMLCanvasElement) => ChartInstance | undefined;
}
export interface ChartWindow extends Window {
    MutationObserver:           typeof MutationObserver;
    Chart?:                     ChartGlobal;
    __minmatar_charts_bound?:   boolean;
}

export const CHART_SELECTOR = 'canvas[data-chart]'

const instances = new WeakMap<HTMLCanvasElement, ChartInstance>()

export function parse_spec(canvas: HTMLCanvasElement): ChartSpec | null {
    try {
        return JSON.parse(canvas.dataset.chart ?? '') as ChartSpec
    } catch {
        return null
    }
}

export function destroy_chart(win: ChartWindow, canvas: HTMLCanvasElement) {
    instances.get(canvas)?.destroy()
    instances.delete(canvas)
    win.Chart?.getChart?.(canvas)?.destroy()
}

/** Chart one canvas. A canvas already charted is left alone. Returns whether a chart now exists. */
export function mount_chart(win: ChartWindow, canvas: HTMLCanvasElement): boolean {
    if (instances.has(canvas)) return true
    if (!win.Chart) return false
    const spec = parse_spec(canvas)
    if (!spec) return false

    const reduce_motion = win.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    // Chart.js refuses a canvas it already owns.
    win.Chart.getChart?.(canvas)?.destroy()
    instances.set(canvas, new win.Chart(canvas, build_config(spec, css_token_reader(win), reduce_motion)))
    return true
}

const canvases_in = (node: Node): HTMLCanvasElement[] => {
    if (!(node instanceof Element)) return []
    const found = [...node.querySelectorAll<HTMLCanvasElement>(CHART_SELECTOR)]
    return node.matches(CHART_SELECTOR) ? [node as HTMLCanvasElement, ...found] : found
}

/**
 * Chart every `canvas[data-chart]` on the page and keep following it: canvases
 * added later (htmx swaps, navigation) are charted, canvases removed are
 * destroyed. Safe to call twice.
 */
export function bind_charts(win: ChartWindow) {
    if (win.__minmatar_charts_bound) return
    win.__minmatar_charts_bound = true

    const doc = win.document
    const mount_all = (root: ParentNode) => root.querySelectorAll<HTMLCanvasElement>(CHART_SELECTOR).forEach((canvas) => mount_chart(win, canvas))

    const observer = new win.MutationObserver((records) => {
        for (const record of records) {
            record.removedNodes.forEach((node) => canvases_in(node).forEach((canvas) => { if (!canvas.isConnected) destroy_chart(win, canvas) }))
            record.addedNodes.forEach((node) => canvases_in(node).forEach((canvas) => mount_chart(win, canvas)))
        }
    })
    observer.observe(doc.documentElement, { childList: true, subtree: true })

    // Chart.js is a CDN script; if it has not run yet, chart what is waiting once it has.
    if (win.Chart) mount_all(doc)
    else win.addEventListener('load', () => mount_all(doc), { once: true })
}
