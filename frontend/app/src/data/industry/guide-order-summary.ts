/**
 * Guide hull manufacturing order summary (static report).
 *
 * Baked from Amamake compressed-ore planner + Jita sell · qty 100 · 25M+ x100 filter.
 * Refresh: `pipenv run python manage.py export_guide_order_summary`
 *
 * As-of: 22 Jul 2026
 */

export const AS_OF_DATE = '22 Jul 2026'
export const ORDER_QTY = 100
export const MIN_ORDER_PROFIT_ISK = 25_000_000
export const FACILITY_KEY = 'amamake'

/** ISK/LP used when this snapshot was baked (not necessarily live production defaults). */
export const LP_RATES = {
    Minmatar: 850,
    Caldari: 925,
    Amarr: 1000,
    Gallente: 1000,
} as const

export type GuideOrderHullKind = 'Navy' | 'T1'
export type GuideOrderFaction =
    | 'Amarr'
    | 'Caldari'
    | 'Gallente'
    | 'Minmatar'
    | 'T1'

export type GuideOrderRow = {
    name: string
    typeId: number
    kind: GuideOrderHullKind
    faction: GuideOrderFaction
    iskPerLp: number | null
    costPer: number
    jitaSell: number
    profitPer: number
    orderProfit: number
    note?: string
}

export type GuideOrderTableTone = 'info' | 'success' | 'warning' | 'danger'

export type GuideOrderTableRow = {
    cells: readonly string[]
    tone?: GuideOrderTableTone
}

/** Kept lines only (explicit cuts + under 25M x100 removed). */
export const GUIDE_ORDER_ROWS: readonly GuideOrderRow[] = [
    {
        name: 'Caldari Navy Hookbill',
        typeId: 17619,
        kind: 'Navy',
        faction: 'Caldari',
        iskPerLp: 925,
        costPer: 7_107_908,
        jitaSell: 8_000_000,
        profitPer: 892_092,
        orderProfit: 89_209_200,
    },
    {
        name: 'Federation Navy Comet',
        typeId: 17841,
        kind: 'Navy',
        faction: 'Gallente',
        iskPerLp: 1000,
        costPer: 7_407_908,
        jitaSell: 8_465_000,
        profitPer: 1_057_092,
        orderProfit: 105_709_203,
    },
    {
        name: 'Imperial Navy Slicer',
        typeId: 17703,
        kind: 'Navy',
        faction: 'Amarr',
        iskPerLp: 1000,
        costPer: 7_407_908,
        jitaSell: 10_000_000,
        profitPer: 2_592_092,
        orderProfit: 259_209_203,
    },
    {
        name: 'Republic Fleet Firetail',
        typeId: 17812,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 6_807_908,
        jitaSell: 8_998_000,
        profitPer: 2_190_092,
        orderProfit: 219_009_203,
    },
    {
        name: 'Vigil Fleet Issue',
        typeId: 37454,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 6_807_908,
        jitaSell: 11_490_000,
        profitPer: 4_682_092,
        orderProfit: 468_209_203,
    },
    {
        name: 'Coercer Navy Issue',
        typeId: 73789,
        kind: 'Navy',
        faction: 'Amarr',
        iskPerLp: 1000,
        costPer: 17_548_217,
        jitaSell: 21_300_000,
        profitPer: 3_751_783,
        orderProfit: 375_178_295,
    },
    {
        name: 'Thrasher Fleet Issue',
        typeId: 73794,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 15_748_217,
        jitaSell: 18_840_000,
        profitPer: 3_091_783,
        orderProfit: 309_178_295,
    },
    {
        name: 'Cormorant Navy Issue',
        typeId: 73795,
        kind: 'Navy',
        faction: 'Caldari',
        iskPerLp: 925,
        costPer: 16_648_217,
        jitaSell: 18_000_000,
        profitPer: 1_351_783,
        orderProfit: 135_178_300,
    },
    {
        name: 'Talwar Fleet Issue',
        typeId: 91858,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 15_748_217,
        jitaSell: 19_522_645,
        profitPer: 3_774_428,
        orderProfit: 377_442_795,
        note: 'BOM proxied (identical navy destroyer recipe)',
    },
    {
        name: 'Coercer',
        typeId: 16236,
        kind: 'T1',
        faction: 'T1',
        iskPerLp: null,
        costPer: 1_047_349,
        jitaSell: 1_386_000,
        profitPer: 338_651,
        orderProfit: 33_865_146,
    },
    {
        name: 'Arbitrator',
        typeId: 628,
        kind: 'T1',
        faction: 'T1',
        iskPerLp: null,
        costPer: 8_480_564,
        jitaSell: 9_198_000,
        profitPer: 717_436,
        orderProfit: 71_743_589,
    },
    {
        name: 'Augoror Navy Issue',
        typeId: 29337,
        kind: 'Navy',
        faction: 'Amarr',
        iskPerLp: 1000,
        costPer: 41_015_110,
        jitaSell: 43_560_000,
        profitPer: 2_544_890,
        orderProfit: 254_489_050,
    },
    {
        name: 'Omen Navy Issue',
        typeId: 17709,
        kind: 'Navy',
        faction: 'Amarr',
        iskPerLp: 1000,
        costPer: 41_015_110,
        jitaSell: 44_230_000,
        profitPer: 3_214_890,
        orderProfit: 321_489_050,
    },
    {
        name: 'Caracal Navy Issue',
        typeId: 17634,
        kind: 'Navy',
        faction: 'Caldari',
        iskPerLp: 925,
        costPer: 39_665_110,
        jitaSell: 40_000_000,
        profitPer: 334_890,
        orderProfit: 33_489_050,
    },
    {
        name: 'Osprey Navy Issue',
        typeId: 29340,
        kind: 'Navy',
        faction: 'Caldari',
        iskPerLp: 925,
        costPer: 39_665_110,
        jitaSell: 40_930_000,
        profitPer: 1_264_890,
        orderProfit: 126_489_050,
    },
    {
        name: 'Bellicose',
        typeId: 630,
        kind: 'T1',
        faction: 'T1',
        iskPerLp: null,
        costPer: 11_307_191,
        jitaSell: 11_790_000,
        profitPer: 482_809,
        orderProfit: 48_280_913,
    },
    {
        name: 'Scythe Fleet Issue',
        typeId: 29336,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 38_315_110,
        jitaSell: 42_840_000,
        profitPer: 4_524_890,
        orderProfit: 452_489_050,
    },
    {
        name: 'Stabber',
        typeId: 622,
        kind: 'T1',
        faction: 'T1',
        iskPerLp: null,
        costPer: 11_307_191,
        jitaSell: 11_620_000,
        profitPer: 312_809,
        orderProfit: 31_280_913,
    },
    {
        name: 'Stabber Fleet Issue',
        typeId: 17713,
        kind: 'Navy',
        faction: 'Minmatar',
        iskPerLp: 850,
        costPer: 38_315_110,
        jitaSell: 43_340_000,
        profitPer: 5_024_890,
        orderProfit: 502_489_050,
    },
]

export const CUTS_APPLIED =
    'Removed Dragoon, Thrasher, Omen, Maller, Breacher. Also cut any line under 25M on the x100: Tristan, Algos, Catalyst NI, Exequror NI, Vexor, Vexor NI.'

export const ASSUMPTIONS_TEXT =
    `Qty ${ORDER_QTY} per hull. Navy BPCs ME0/TE0 from FW LP store (Minmatar ${LP_RATES.Minmatar}, Caldari ${LP_RATES.Caldari}, Amarr ${LP_RATES.Amarr}, Gallente ${LP_RATES.Gallente} ISK/LP). T1 assumes researched ME10/TE20 BPO (no LP). Amamake Sotiyo + Tatara compressed-ore shopping, Jita to Amamake freight, revenue = Jita sell x ${ORDER_QTY} (no broker/sales tax). Talwar FI uses the same navy destroyer BOM.`

export function formatIskCompact(isk: number): string {
    const abs = Math.abs(isk)
    const sign = isk < 0 ? '-' : ''
    if (abs >= 1_000_000_000) {
        return `${sign}${(abs / 1_000_000_000).toFixed(2)}B`
    }
    if (abs >= 1_000_000) {
        return `${sign}${(abs / 1_000_000).toFixed(2)}M`
    }
    if (abs >= 1_000) {
        return `${sign}${(abs / 1_000).toFixed(0)}k`
    }
    return `${sign}${abs.toFixed(0)}`
}

export function formatIskFull(isk: number): string {
    return Math.round(isk).toLocaleString('en-US')
}

export function shortHullName(name: string): string {
    return name
        .replace(' Navy Issue', ' NI')
        .replace(' Fleet Issue', ' FI')
        .replace('Caldari Navy ', '')
        .replace('Federation Navy ', '')
        .replace('Imperial Navy ', '')
        .replace('Republic Fleet ', '')
}

export function rowTone(orderProfit: number): GuideOrderTableTone {
    if (orderProfit >= 100_000_000) return 'success'
    if (orderProfit >= MIN_ORDER_PROFIT_ISK) return 'info'
    return 'danger'
}

export function sortedByOrderProfit(
    rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS,
): GuideOrderRow[] {
    return [...rows].sort((a, b) => b.orderProfit - a.orderProfit)
}

export function orderTotals(rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS) {
    const totalProfit = rows.reduce((sum, r) => sum + r.orderProfit, 0)
    const navyRows = rows.filter((r) => r.kind === 'Navy')
    const t1Rows = rows.filter((r) => r.kind === 'T1')
    const sorted = sortedByOrderProfit(rows)
    return {
        totalProfit,
        hullCount: rows.length,
        navyCount: navyRows.length,
        t1Count: t1Rows.length,
        navyProfit: navyRows.reduce((sum, r) => sum + r.orderProfit, 0),
        t1Profit: t1Rows.reduce((sum, r) => sum + r.orderProfit, 0),
        best: sorted[0],
        worst: sorted[sorted.length - 1],
        sorted,
    }
}

export function keptOrderTableRows(
    rows: readonly GuideOrderRow[] = GUIDE_ORDER_ROWS,
): GuideOrderTableRow[] {
    return rows.map((r) => ({
        cells: [
            r.name,
            r.iskPerLp == null ? '-' : String(r.iskPerLp),
            formatIskCompact(r.costPer),
            formatIskCompact(r.jitaSell),
            formatIskFull(r.profitPer),
            formatIskCompact(r.orderProfit),
        ] as const,
        tone: rowTone(r.orderProfit),
    }))
}
