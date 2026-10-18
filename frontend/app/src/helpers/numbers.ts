export const number_name = (val: number, locale:string) => {
    if (val < 1000)
        return '';

    const shorten_number:string = Intl.NumberFormat(
        locale,
        {
            notation: "compact",       
            compactDisplay: "long",
            maximumFractionDigits: 1
        }
    ).format(val)
    
    return `${is_approxixmation(shorten_number, val) ? '≈ ' : ''}${shorten_number}`;
}

function is_approxixmation(shorten_number:string, val:number):boolean {
    // Multiplying by 10 to remove floating point error
    return ( (10*val)%(10*parseFloat(shorten_number.split(' ')[0])) != 0 );
}

export const number_thousand_separator = (val: number, locale:string = 'en-US') => {
    return val.toLocaleString(locale, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    })
}

/**
 * Converts a number to a string with a suffix (k, M, B, T).
 * @param num The number to format
 * @param digits The number of decimal places to keep
 */ 
export function format_number(num: number, digits: number = 1): string {
    const lookup = [
        { value: 1, symbol: "" },
        { value: 1e3, symbol: "k" },
        { value: 1e6, symbol: "M" },
        { value: 1e9, symbol: "B" },
        { value: 1e12, symbol: "T" },
        { value: 1e15, symbol: "P" },
        { value: 1e18, symbol: "E" }
    ];

    const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
    const item = lookup.slice().reverse().find((item) => {
        return num >= item.value;
    });

    return item 
        ? (num / item.value).toFixed(digits).replace(rx, "$1") + item.symbol 
        : "0";
}

/**
 * One step of a compact number format: values at or above `min` are divided
 * by `divisor` and shown with `digits` decimals and `suffix`.
 */
export interface CompactTier {
    min: number
    divisor: number
    digits: number
    suffix: string
}

/**
 * A compact number format. The algorithm is shared; each named format below
 * is one page family's display rule, kept so that page reads the same.
 */
export interface CompactFormat {
    /** Largest first. */
    tiers: readonly CompactTier[]
    /**
     * Below the smallest tier: 'plain' shows the rounded whole number,
     * 'smallest_tier' keeps the smallest unit ("0K", "1K").
     */
    small: 'plain' | 'smallest_tier'
    /** Drop trailing zeros after rounding ("1.50B" -> "1.5B", "2.0M" -> "2M"). */
    trim_zeros?: boolean
    /** Sign for negative values (default '-'). */
    minus?: string
    /** Sign for positive values (default none). */
    plus?: string
}

const tier = (min: number, divisor: number, digits: number, suffix: string): CompactTier =>
    ({ min, divisor, digits, suffix })

/** Site default: 1.25T, 2.3B, 12M, 31K, 950. */
export const ISK_COMPACT: CompactFormat = {
    tiers: [
        tier(1e12, 1e12, 2, 'T'),
        tier(1e9, 1e9, 1, 'B'),
        tier(1e6, 1e6, 0, 'M'),
        tier(1e3, 1e3, 0, 'K'),
    ],
    small: 'plain',
}

/** Campaign retrospectives: the site default, but small values stay in K ("0K"). */
export const ISK_COMPACT_ARCHIVE: CompactFormat = {
    ...ISK_COMPACT,
    small: 'smallest_tier',
}

const REPORT_TIERS: readonly CompactTier[] = [
    tier(1e12, 1e12, 2, 'T'),
    tier(1e11, 1e9, 0, 'B'),
    tier(1e9, 1e9, 2, 'B'),
    tier(1e6, 1e6, 0, 'M'),
]

/** Monthly reports (Amamake market): 1.25T, 186B, 16.80B, 17M, 31k. */
export const ISK_REPORT: CompactFormat = {
    tiers: [...REPORT_TIERS, tier(1e3, 1e3, 0, 'k')],
    small: 'smallest_tier',
}

/** Warzone report: like ISK_REPORT, but nothing smaller than M. */
export const ISK_REPORT_MILLIONS: CompactFormat = {
    tiers: REPORT_TIERS,
    small: 'smallest_tier',
}

/** Per-unit prices in the reports: millions as ISK_REPORT, then 31.3k, 950. */
export const ISK_REPORT_UNIT: CompactFormat = {
    tiers: [...REPORT_TIERS, tier(1e3, 1e3, 1, 'k')],
    small: 'plain',
}

/** Two-decimal millions for guide order tables: 1.25B, 16.80M, 31k, -950. */
export const ISK_COMPACT_PRECISE: CompactFormat = {
    tiers: [
        tier(1e9, 1e9, 2, 'B'),
        tier(1e6, 1e6, 2, 'M'),
        tier(1e3, 1e3, 0, 'k'),
    ],
    small: 'plain',
}

/** Contract price ledgers: 1.25B, 150M, 16.8M, 31k, with a true minus sign. */
export const ISK_CONTRACT: CompactFormat = {
    tiers: [
        tier(1e9, 1e9, 2, 'B'),
        tier(1e8, 1e6, 0, 'M'),
        tier(1e6, 1e6, 1, 'M'),
        tier(1e3, 1e3, 0, 'k'),
    ],
    small: 'plain',
    minus: '\u2212',
}

/** Three significant figures for table cells: 113M, 14.9M, 600K, 950. */
export const SHORT_AMOUNT: CompactFormat = {
    tiers: [
        tier(1e14, 1e12, 0, 'T'),
        tier(1e12, 1e12, 1, 'T'),
        tier(1e11, 1e9, 0, 'B'),
        tier(1e9, 1e9, 1, 'B'),
        tier(1e8, 1e6, 0, 'M'),
        tier(1e6, 1e6, 1, 'M'),
        tier(1e5, 1e3, 0, 'K'),
        tier(1e3, 1e3, 1, 'K'),
    ],
    small: 'plain',
    trim_zeros: true,
}

const PLAIN_TIER: CompactTier = tier(0, 1, 0, '')

function tier_text(abs: number, step: CompactTier, trim_zeros: boolean): string {
    const text = (abs / step.divisor).toFixed(step.digits)
    return trim_zeros && text.includes('.') ? text.replace(/\.?0+$/, '') : text
}

/**
 * Format a number with a compact format. `null`, `undefined` and non-finite
 * values return `empty`. When rounding carries a value into the next unit
 * ("1000K"), it is shown in that unit instead ("1M").
 */
export function format_compact(
    value: number | null | undefined,
    format: CompactFormat = ISK_COMPACT,
    empty: string = '—',
): string {
    if (value == null || !Number.isFinite(value))
        return empty

    const abs = Math.abs(value)
    const sign = value < 0 ? (format.minus ?? '-') : value > 0 ? (format.plus ?? '') : ''
    const tiers = format.tiers
    const trim_zeros = format.trim_zeros ?? false

    let index = tiers.findIndex(step => abs >= step.min)
    if (index === -1 && format.small === 'smallest_tier')
        index = tiers.length - 1

    let step = index === -1 ? PLAIN_TIER : tiers[index]
    let text = index === -1 ? String(Math.round(abs)) : tier_text(abs, step, trim_zeros)

    // Promote "1000K" to "1M": only across a unit change, never between two
    // precisions of the same unit.
    let next = index === -1 ? tiers.length - 1 : index - 1
    while (next >= 0 && tiers[next].divisor > step.divisor && Number(text) * step.divisor >= tiers[next].min) {
        index = next
        step = tiers[index]
        text = tier_text(abs, step, trim_zeros)
        next = index - 1
    }

    return `${sign}${text}${step.suffix}`
}

/**
 * Compact ISK (site default format). Null-safe: missing values show `empty`.
 * `suffix` is appended to real values only (e.g. ' ISK').
 */
export function format_isk(
    value: number | null | undefined,
    options: { suffix?: string, empty?: string, format?: CompactFormat } = {},
): string {
    const empty = options.empty ?? '—'
    if (value == null || !Number.isFinite(value))
        return empty
    return `${format_compact(value, options.format ?? ISK_COMPACT, empty)}${options.suffix ?? ''}`
}

/** Whole ISK with thousands separators ("1,234,568"). Null-safe. */
export function format_isk_full(
    value: number | null | undefined,
    locale: string = 'en-US',
    empty: string = '—',
): string {
    if (value == null || !Number.isFinite(value))
        return empty
    return number_thousand_separator(Math.round(value), locale)
}

export function format_volume_m3(volume: number): string {
    if (!Number.isFinite(volume))
        return '0'
    return format_number(volume)
}

export function format_hours(hours: number): string {
    if (!Number.isFinite(hours))
        return '0'
    const rounded = Math.round(hours * 10) / 10
    if (Number.isInteger(rounded))
        return String(rounded)
    return rounded.toFixed(1)
}