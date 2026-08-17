export function health_confidence_label(
    conf: string | null | undefined,
    t: (key: string) => string,
): string | null {
    switch (conf) {
        case 'high':
            return t('alliance.health.conf.high')
        case 'medium':
            return t('alliance.health.conf.medium')
        case 'low':
            return t('alliance.health.conf.low')
        default:
            return null
    }
}

export type AllianceHealthOrderKind = 'number' | 'text'
export type AllianceHealthOrderDir = 'asc' | 'desc'

export interface AllianceHealthOrderOption {
    id: string
    label: string
    kind: AllianceHealthOrderKind
}

export type AllianceHealthMetricScale = 'higher' | 'lower' | 'none'
export type AllianceHealthMetricTone = 'good' | 'bad'

export interface AllianceHealthPilotMetric {
    id: string
    label: string
    value: string
    sort: number | string
    scale?: AllianceHealthMetricScale
    tone?: AllianceHealthMetricTone
    typical?: string
}

export interface AllianceHealthPilotTag {
    text: string
    color?: string
}

export interface AllianceHealthPilotAction {
    label: string
    confirm_title: string
    confirm_content: string
    post_url: string
    target: string
}

export interface AllianceHealthPilotListRow {
    name: string
    corp: string
    character_id?: number | null
    corporation_id?: number | null
    search_text: string
    timezone?: string | null
    note?: string
    tags?: AllianceHealthPilotTag[]
    metrics: AllianceHealthPilotMetric[]
    action?: AllianceHealthPilotAction
}

export function default_health_order_dir(
    kind: AllianceHealthOrderKind,
): AllianceHealthOrderDir {
    switch (kind) {
        case 'text':
            return 'asc'
        case 'number':
            return 'desc'
        default: {
            const _never: never = kind
            return _never
        }
    }
}

export function next_health_order_state(
    current_order_by: string,
    current_dir: AllianceHealthOrderDir,
    clicked_id: string,
    kinds: Record<string, AllianceHealthOrderKind>,
): { order_by: string; order_dir: AllianceHealthOrderDir } {
    if (clicked_id === current_order_by) {
        return {
            order_by: current_order_by,
            order_dir: current_dir === 'asc' ? 'desc' : 'asc',
        }
    }
    const kind = kinds[clicked_id] ?? 'number'
    return {
        order_by: clicked_id,
        order_dir: default_health_order_dir(kind),
    }
}

export function compare_health_sort_values(
    a: string,
    b: string,
    kind: AllianceHealthOrderKind,
    direction: AllianceHealthOrderDir,
): number {
    const dir = direction === 'asc' ? 1 : -1
    switch (kind) {
        case 'number': {
            const an = Number(a)
            const bn = Number(b)
            const a_miss = a === '' || Number.isNaN(an)
            const b_miss = b === '' || Number.isNaN(bn)
            if (a_miss && b_miss) return 0
            if (a_miss) return 1
            if (b_miss) return -1
            if (an === bn) return 0
            return (an < bn ? -1 : 1) * dir
        }
        case 'text': {
            const cmp = a.localeCompare(b, undefined, { sensitivity: 'base' })
            return cmp * dir
        }
        default: {
            const _never: never = kind
            return _never
        }
    }
}

export function sort_value_attr(value: number | string | null | undefined): string {
    if (value == null || value === '') return ''
    if (typeof value === 'number' && Number.isNaN(value)) return ''
    return String(value)
}

export function metric_number(sort: number | string): number | null {
    if (sort === '') return null
    const n = Number(sort)
    return Number.isNaN(n) ? null : n
}

export function median_numbers(values: number[]): number | null {
    if (values.length < 3) return null
    const xs = [...values].sort((a, b) => a - b)
    const mid = Math.floor(xs.length / 2)
    return xs.length % 2 === 1 ? xs[mid] : (xs[mid - 1] + xs[mid]) / 2
}

export function format_metric_typical(sample_value: string, median: number): string {
    const rounded = Number.isInteger(median)
        ? String(median)
        : String(Math.round(median * 10) / 10)
    if (sample_value.endsWith('h')) return `${rounded}h`
    if (sample_value.endsWith('d')) return `${rounded}d`
    return rounded
}

export function tone_vs_median(
    value: number,
    median: number,
    scale: AllianceHealthMetricScale,
): AllianceHealthMetricTone | undefined {
    switch (scale) {
        case 'none':
            return undefined
        case 'higher': {
            if (median === 0) return value > 0 ? 'good' : undefined
            const ratio = value / median
            if (ratio >= 2) return 'good'
            if (ratio <= 0.5) return 'bad'
            return undefined
        }
        case 'lower': {
            if (median === 0) return value > 0 ? 'bad' : undefined
            const ratio = value / median
            if (ratio >= 2) return 'bad'
            if (ratio <= 0.5) return 'good'
            return undefined
        }
        default: {
            const _never: never = scale
            return _never
        }
    }
}

export function apply_list_metric_tones(
    rows: AllianceHealthPilotListRow[],
): AllianceHealthPilotListRow[] {
    const ids = [...new Set(rows.flatMap((row) => row.metrics.map((metric) => metric.id)))]
    const typical_by_id: Record<string, string> = {}
    const median_by_id: Record<string, number> = {}

    for (const id of ids) {
        const samples = rows.flatMap((row) =>
            row.metrics.filter((metric) => metric.id === id),
        )
        const first = samples[0]
        const scale = first?.scale ?? 'higher'
        if (!first || scale === 'none') continue
        const numbers = samples
            .map((metric) => metric_number(metric.sort))
            .filter((n): n is number => n != null)
        const median = median_numbers(numbers)
        if (median == null) continue
        median_by_id[id] = median
        typical_by_id[id] = format_metric_typical(first.value, median)
    }

    return rows.map((row) => ({
        ...row,
        metrics: row.metrics.map((metric) => {
            const median = median_by_id[metric.id]
            const typical = typical_by_id[metric.id]
            const value = metric_number(metric.sort)
            const scale = metric.scale ?? 'higher'
            if (median == null || value == null || typical == null) return metric
            return {
                ...metric,
                typical,
                tone: tone_vs_median(value, median, scale),
            }
        }),
    }))
}

export function csv_escape_field(value: string): string {
    if (/[",\n\r]/.test(value)) return `"${value.replace(/"/g, '""')}"`
    return value
}

export function csv_from_matrix(rows: readonly (readonly string[])[]): string {
    return (
        rows
            .map((row) => row.map((cell) => csv_escape_field(String(cell ?? ''))).join(','))
            .join('\n') + '\n'
    )
}

export function csv_record_from_pilot(row: AllianceHealthPilotListRow): string[] {
    return [
        row.name,
        row.corp,
        row.timezone ?? '',
        ...row.metrics.map((metric) => metric.value),
        row.note ?? '',
    ]
}

export function csv_headers_from_pilot(
    row: AllianceHealthPilotListRow | undefined,
    labels: { pilot: string; corp: string; tz: string; note: string },
): string[] {
    return [
        labels.pilot,
        labels.corp,
        labels.tz,
        ...(row?.metrics ?? []).map((metric) => metric.label),
        labels.note,
    ]
}

