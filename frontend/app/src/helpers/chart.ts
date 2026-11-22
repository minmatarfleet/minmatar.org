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
    [key: string]: any;
}

export type ChartKind = 'line' | 'bar' | 'doughnut' | 'pie' | 'radar'

export interface ChartSpec {
    type:       ChartKind;
    labels:     (string | number)[];
    datasets:   ChartDataset[];
    options?:   Record<string, any>;
    legend?:    boolean;
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
    const { tone, tones, fill, ...rest } = dataset
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
    const filled = fill ?? type === 'radar'
    return {
        ...rest,
        borderColor: color,
        backgroundColor: filled ? with_alpha(color, 20) : color,
        pointBackgroundColor: color,
        pointBorderColor: color,
        fill: filled,
        tension: rest.tension ?? 0.25,
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
            },
        },
    }

    if (spec.type === 'line' || spec.type === 'bar') {
        defaults.scales = {
            x: { grid: { color: border }, ticks: { color: faded }, border: { color: border } },
            y: { grid: { color: border }, ticks: { color: faded }, border: { color: border }, beginAtZero: true },
        }
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
