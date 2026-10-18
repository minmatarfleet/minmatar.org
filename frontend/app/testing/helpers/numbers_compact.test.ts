import { describe, expect, it } from 'vitest'

import {
    ISK_COMPACT,
    ISK_COMPACT_ARCHIVE,
    ISK_COMPACT_PRECISE,
    ISK_CONTRACT,
    ISK_REPORT,
    ISK_REPORT_MILLIONS,
    ISK_REPORT_UNIT,
    SHORT_AMOUNT,
    format_compact,
    format_isk,
    format_isk_full,
} from '@helpers/numbers'
import { format_short_amount } from '@helpers/loyalty_offers_rows'
import { format_isk as report_format_isk, format_unit_isk } from '@/data/amamake-market/format'
import { formatIsk as campaign_format_isk } from '@/data/campaigns'
import { formatIskCompact, formatIskFull } from '@/data/industry/guide-order-summary'

/*
 * Parity table: each `legacy_*` is a verbatim copy of a formatter that was
 * replaced by a named CompactFormat. The new output must equal the old one
 * for every sample, except the cases listed in INTENDED (bugs in the old
 * rule: "1000K" instead of "1M", campaign negatives shown as "-5000K").
 */

function legacy_format_isk(isk: number): string {
    const abs = Math.abs(isk)
    if (abs >= 1_000_000_000_000)
        return `${(isk / 1_000_000_000_000).toFixed(2)}T`
    if (abs >= 1_000_000_000)
        return `${(isk / 1_000_000_000).toFixed(1)}B`
    if (abs >= 1_000_000)
        return `${(isk / 1_000_000).toFixed(0)}M`
    if (abs >= 1_000)
        return `${(isk / 1_000).toFixed(0)}K`
    return isk.toFixed(0)
}

// data/campaigns/{hek,auga,providence,scalding-pass,etherium-reach,kamela}.ts
function legacy_campaign_format_isk(isk: number): string {
    if (isk >= 1_000_000_000_000) return `${(isk / 1_000_000_000_000).toFixed(2)}T`
    if (isk >= 1_000_000_000) return `${(isk / 1_000_000_000).toFixed(1)}B`
    if (isk >= 1_000_000) return `${(isk / 1_000_000).toFixed(0)}M`
    return `${(isk / 1_000).toFixed(0)}K`
}

// data/amamake-market/format.ts
function legacy_report_format_isk(value: number): string {
    if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 100_000_000_000) return `${Math.round(value / 1_000_000_000)}B`
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(0)}M`
    return `${(value / 1_000).toFixed(0)}k`
}

function legacy_report_format_unit_isk(value: number): string {
    if (value >= 1_000_000) return legacy_report_format_isk(value)
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
    return `${Math.round(value)}`
}

// components/blocks/warzone/WarzoneReportIssue.astro
function legacy_warzone_format_isk(value: number): string {
    if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 100_000_000_000) return `${Math.round(value / 1_000_000_000)}B`
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
    return `${(value / 1_000_000).toFixed(0)}M`
}

// data/industry/guide-order-summary.ts formatIskCompact
function legacy_guide_format_isk_compact(isk: number): string {
    const abs = Math.abs(isk)
    const sign = isk < 0 ? '-' : ''
    if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(2)}B`
    if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}M`
    if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(0)}k`
    return `${sign}${abs.toFixed(0)}`
}

// components/blocks/FittingBuyOrderContractPrices.astro fmt_compact
function legacy_contract_fmt_compact(num: number | null, signed = false): string {
    if (num == null) return '—'
    const abs = Math.abs(num)
    const sign = num < 0 ? '−' : (signed && num > 0 ? '+' : '')
    let body: string
    if (abs >= 1e9) body = `${(abs / 1e9).toFixed(2)}B`
    else if (abs >= 1e8) body = `${(abs / 1e6).toFixed(0)}M`
    else if (abs >= 1e6) body = `${(abs / 1e6).toFixed(1)}M`
    else if (abs >= 1e3) body = `${(abs / 1e3).toFixed(0)}k`
    else body = Math.round(abs).toLocaleString('en-US')
    return `${sign}${body}`
}

// helpers/loyalty_offers_rows.ts format_short_amount
const LEGACY_SHORT_UNITS: Array<[number, string]> = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']]
function legacy_format_short_amount(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value)) return '—'
    if (value <= 0) return '0'
    for (let index = 0; index < LEGACY_SHORT_UNITS.length; index++) {
        const [size, suffix] = LEGACY_SHORT_UNITS[index]
        if (value < size) continue
        const scaled = value / size
        const text = scaled.toFixed(scaled >= 100 ? 0 : 1).replace(/\.0$/, '')
        if (Number(text) >= 1000 && index > 0)
            return `${(value / LEGACY_SHORT_UNITS[index - 1][0]).toFixed(1).replace(/\.0$/, '')}${LEGACY_SHORT_UNITS[index - 1][1]}`
        return `${text}${suffix}`
    }
    return String(Math.round(value))
}

// Wrappers: BuybackStockLedger/BuybackStockMetrics format_value, ProductBuildCost isk.
function legacy_isk_or_dash(value: number | null | undefined, suffix = ''): string {
    if (value == null) return '—'
    return `${legacy_format_isk(value)}${suffix}`
}

// market/buyback/appraisal.astro local format_isk
function legacy_appraisal_full(value: number | null): string {
    if (value == null) return '—'
    return Math.round(value).toLocaleString('en-US')
}

const SAMPLES = [
    0, 0.4, 0.5, 12.5, 999, 999.6, 1_000, 1_499, 12_345, 99_960, 100_000, 123_456,
    999_499, 999_999, 1_000_000, 1_500_000, 14_949_999, 16_800_000, 99_960_000,
    100_000_000, 123_456_789, 999_400_000, 999_999_999, 1_000_000_000, 2_300_000_000,
    16_804_000_000, 99_996_000_000, 100_000_000_000, 186_400_000_000, 999_960_000_000,
    1_000_000_000_000, 1_254_000_000_000, 123_456_000_000_000,
    -0.4, -999, -1_500, -5_000_000, -2_300_000_000,
]

type Variant = {
    name: string
    legacy: (value: number) => string
    current: (value: number) => string
    /** Values whose display changes on purpose: [value, new display]. */
    intended?: Array<[number, string]>
    /** Values outside this variant's real inputs (e.g. negatives for static report data). */
    skip?: (value: number) => boolean
}

const VARIANTS: Variant[] = [
    {
        name: 'format_isk (site default)',
        legacy: legacy_format_isk,
        current: value => format_isk(value),
        intended: [
            [999.6, '1K'], [999_999, '1M'], [999_999_999, '1.0B'], [999_960_000_000, '1.00T'],
        ],
    },
    {
        name: 'campaign formatIsk',
        legacy: legacy_campaign_format_isk,
        current: value => campaign_format_isk(value),
        intended: [
            [999_999, '1M'], [999_999_999, '1.0B'], [999_960_000_000, '1.00T'],
            // Negatives never reach these static retrospectives, but the old rule
            // fell through to K ("-5000K").
            [-5_000_000, '-5M'], [-2_300_000_000, '-2.3B'],
        ],
    },
    {
        name: 'amamake report format_isk',
        legacy: legacy_report_format_isk,
        current: value => report_format_isk(value),
        intended: [[999_999, '1M'], [999_999_999, '1.00B'], [999_960_000_000, '1.00T']],
        skip: value => value < 0,
    },
    {
        name: 'amamake report format_unit_isk',
        legacy: legacy_report_format_unit_isk,
        current: value => format_unit_isk(value),
        intended: [[999.6, '1.0k'], [999_999, '1M'], [999_999_999, '1.00B'], [999_960_000_000, '1.00T']],
        skip: value => value < 0,
    },
    {
        name: 'warzone format_isk',
        legacy: legacy_warzone_format_isk,
        current: value => format_compact(value, ISK_REPORT_MILLIONS),
        intended: [[999_999_999, '1.00B'], [999_960_000_000, '1.00T']],
        skip: value => value < 0,
    },
    {
        name: 'guide formatIskCompact',
        legacy: legacy_guide_format_isk_compact,
        current: value => formatIskCompact(value),
        intended: [[999.6, '1k'], [999_999, '1.00M'], [999_999_999, '1.00B']],
        // The old rule had no T unit; guide figures stay far below 1T.
        skip: value => Math.abs(value) >= 999_995_000_000,
    },
    {
        name: 'contract fmt_compact',
        legacy: value => legacy_contract_fmt_compact(value),
        current: value => format_compact(value, ISK_CONTRACT),
        intended: [[999.6, '1k'], [999_999, '1.0M'], [999_999_999, '1.00B']],
        skip: value => Math.abs(value) >= 999_995_000_000,
    },
    {
        name: 'contract fmt_compact (signed)',
        legacy: value => legacy_contract_fmt_compact(value, true),
        current: value => format_compact(value, { ...ISK_CONTRACT, plus: '+' }),
        intended: [[999.6, '+1k'], [999_999, '+1.0M'], [999_999_999, '+1.00B']],
        skip: value => Math.abs(value) >= 999_995_000_000,
    },
    {
        name: 'loyalty format_short_amount',
        legacy: legacy_format_short_amount,
        current: value => format_short_amount(value),
        intended: [[999.6, '1K']],
    },
]

describe('compact formatter parity with the formatters it replaced', () => {
    for (const variant of VARIANTS) {
        it(variant.name, () => {
            const intended = new Map(variant.intended ?? [])
            for (const value of SAMPLES) {
                if (variant.skip?.(value)) continue
                const expected = intended.has(value) ? intended.get(value) : variant.legacy(value)
                expect(`${value} -> ${variant.current(value)}`).toBe(`${value} -> ${expected}`)
            }
        })

        it(`${variant.name}: intended changes really differ from the old rule`, () => {
            for (const [value, display] of variant.intended ?? []) {
                expect(variant.legacy(value)).not.toBe(display)
            }
        })
    }
})

describe('null-safe wrappers', () => {
    it('format_isk shows a dash for missing values and an optional suffix', () => {
        for (const value of [null, undefined, 0, 1_500_000, -2_300_000_000]) {
            expect(format_isk(value)).toBe(legacy_isk_or_dash(value))
            expect(format_isk(value, { suffix: ' ISK' })).toBe(legacy_isk_or_dash(value, ' ISK'))
        }
        expect(format_isk(Number.NaN)).toBe('—')
        expect(format_isk(null, { empty: '' })).toBe('')
    })

    it('format_isk_full matches the appraisal page full number', () => {
        for (const value of [null, 0, 999.5, 1_234_567.8, -5_000]) {
            expect(format_isk_full(value)).toBe(legacy_appraisal_full(value))
        }
        expect(formatIskFull(1_234_567.8)).toBe('1,234,568')
    })

    it('format_compact returns empty for non-finite values', () => {
        expect(format_compact(Number.POSITIVE_INFINITY)).toBe('—')
        expect(format_compact(undefined, ISK_COMPACT, '')).toBe('')
    })
})

describe('named formats', () => {
    it('cover the representative values', () => {
        const values = [0, -1_500, 999, 1e3, 1.5e6, 2.3e9, 1e12]
        const table = Object.fromEntries(Object.entries({
            ISK_COMPACT, ISK_COMPACT_ARCHIVE, ISK_REPORT, ISK_REPORT_MILLIONS, ISK_REPORT_UNIT,
            ISK_COMPACT_PRECISE, ISK_CONTRACT, SHORT_AMOUNT,
        }).map(([name, format]) => [name, values.map(value => format_compact(value, format))]))
        expect(table).toEqual({
            ISK_COMPACT: ['0', '-2K', '999', '1K', '2M', '2.3B', '1.00T'],
            ISK_COMPACT_ARCHIVE: ['0K', '-2K', '1K', '1K', '2M', '2.3B', '1.00T'],
            ISK_REPORT: ['0k', '-2k', '1k', '1k', '2M', '2.30B', '1.00T'],
            ISK_REPORT_MILLIONS: ['0M', '-0M', '0M', '0M', '2M', '2.30B', '1.00T'],
            ISK_REPORT_UNIT: ['0', '-1.5k', '999', '1.0k', '2M', '2.30B', '1.00T'],
            ISK_COMPACT_PRECISE: ['0', '-2k', '999', '1k', '1.50M', '2.30B', '1000.00B'],
            ISK_CONTRACT: ['0', '−2k', '999', '1k', '1.5M', '2.30B', '1000.00B'],
            SHORT_AMOUNT: ['0', '-1.5K', '999', '1K', '1.5M', '2.3B', '1T'],
        })
    })
})
