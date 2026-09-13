/** Data model for the monthly Amamake Market Report (`/amamake-market/`). */

export type MarketMilitiaId = 'minmatar' | 'amarr'

// ---------------------------------------------------------------------------
// Generated rows (written by scripts/amamake_market_extract.mjs)
// ---------------------------------------------------------------------------

export type MarketSalesDay = {
    date: string
    isk: number
    fills: number
}

export type MarketSalesTotals = {
    isk: number
    isk_label: string
    fills: number
    units: number
    /** Distinct types with at least one inferred fill. */
    types: number
    /**
     * (Amamake fill − Jita − freight/unit) × units, summed over types with a
     * Forge Jita average. Types with no Jita price are omitted, not treated as 0.
     */
    profit: number
    profit_label: string
    /** Types included in `profit` (had a Jita average and units). */
    profit_types: number
    /** Types omitted from `profit` because Jita was missing. */
    profit_unpriced_types: number
    days_with_sales: number
    loudest_day: MarketSalesDay | null
    quietest_day: MarketSalesDay | null
}

export type MarketSalesTotalsVs = {
    isk: number
    isk_pct: number | null
    fills: number
    fills_pct: number | null
    units: number
    units_pct: number | null
    types: number
    profit: number
    profit_pct: number | null
}

export type MarketDayRow = {
    date: string
    isk: number
    fills: number
    units: number
}

export type MarketWeekRow = {
    label: string
    isk: number
    isk_label: string
    fills: number
    units: number
}

export type MarketCategoryRow = {
    name: string
    isk: number
    isk_label: string
    units: number
    fills: number
    /** Share of the month's inferred ISK, percent. */
    share: number
    isk_vs: number
    isk_vs_label: string
    isk_vs_pct: number | null
    units_vs: number
    fills_vs: number
    /** Volume-weighted % over Jita (priced types only). Null when the class has no Forge average. */
    markup_pct: number | null
}

export type MarketContractTotals = {
    count: number
    count_vs: number
    isk: number
    isk_label: string
    isk_vs: number
    unmatched: number
    matched: number
}

export type MarketContractHullRow = {
    typeId: number
    name: string
    group: string
    isk: number
    isk_label: string
    count: number
    isk_vs: number
    count_vs: number
    share: number
}

export type MarketMarginRow = {
    typeId: number
    name: string
    category: string
    units: number
    fills: number
    isk: number
    isk_label: string
    /** Mean inferred fill price at the freeport. */
    amamake_avg: number
    /** Forge daily average (Jita guide) as of JITA_AS_OF. */
    jita: number
    freight: number
    landed: number
    margin: number
    margin_pct: number
    /** (Amamake − Jita − freight) × units. Rank key. */
    extra_isk: number
    extra_isk_label: string
}

export type MarketTopTypeRow = {
    typeId: number
    name: string
    category: string
    isk: number
    isk_label: string
    units: number
    fills: number
    share: number
    /** Month-over-month ISK change in percent; null when the type is new. */
    isk_vs_pct: number | null
    /** Type had no inferred fills the prior month. */
    is_new: boolean
    /** Volume-weighted % over Jita (fill ISK / units vs Forge average). Null when Jita is missing. */
    markup_pct: number | null
}

/** Top inferred-ISK types in each SDE class bucket (Ships, Rigs, …). */
export type MarketTopTypesByClass = Readonly<Record<string, readonly MarketTopTypeRow[]>>

export type MarketHullRow = {
    typeId: number
    name: string
    group: string
    /** Inferred units sold at the freeport. */
    sold: number
    /** Hulls of this type destroyed in the Amarr–Minmatar warzone (capsules excluded). */
    lost: number
    sold_vs: number
    lost_vs: number
    /** sold / lost, or null when nothing was lost. */
    ratio: number | null
}

export type MarketSystemSummary = {
    system_id: number
    ships: number
    ships_vs: number
    isk: number
    isk_label: string
    isk_vs: number
    share_of_warzone: number
    unique_characters: number
    capital_ships: number
    capital_isk: number
    loudest_day: { date: string; ships: number }
    holds_today: MarketMilitiaId
}

export type MarketWarzoneSummary = {
    systems: number
    ships: number
    ships_vs: number
    isk: number
    isk_label: string
    isk_vs: number
}

export type MarketCatchmentRow = {
    system: string
    system_id: number
    region: string
    front: string
    href: string
    ships: number
    ships_vs: number
    isk: number
    isk_label: string
    isk_vs: number
    capital_ships: number
    capital_isk: number
    /** Capital ISK as a percent of the system's ISK destroyed. */
    capital_share: number
    share_of_warzone: number
    holds_today: MarketMilitiaId
}

export type MarketRegionRow = {
    region: string
    front: string
    ships: number
    isk: number
    isk_label: string
    share: number
}

export type MarketPipe = {
    label: string
    systems: readonly string[]
    ships: number
    isk: number
    share: number
}

export type MarketCapitalSplitRow = {
    system: string
    system_id: number
    capital_ships: number
    capital_isk: number
    subcap_isk: number
    capital_isk_label: string
    subcap_isk_label: string
}

export type MarketHubHealth = {
    sell_orders_health_pct: number | null
    sell_orders_viability_pct: number | null
    sell_orders_isk: number | null
    contracts_health_pct: number | null
    contracts_isk: number | null
    synced_at: string | null
}

// ---------------------------------------------------------------------------
// Editorial layer (hand-authored per issue in `<slug>.ts`)
// ---------------------------------------------------------------------------

export type MarketLink = {
    href: string
    label: string
}

export type MarketStat = {
    label: string
    value: string
    note?: string
}

/** A hand-authored table (import vs local). */
export type MarketTable = {
    headers: readonly string[]
    rows: readonly { cells: readonly string[]; tone?: 'success' | 'danger' | 'info' }[]
    footnote: string
}

export type MarketMethodologyEntry = {
    label: string
    text: string
}

export type MarketInvolvementStep = {
    title: string
    text: string
    href: string
    label: string
}

export type AmamakeMarketIssue = {
    slug: string
    permalink_path: string
    cover_image: string
    published_at: Date
    period_utc: string
    /** Short name of the month being compared against, e.g. "July". */
    previous_period_label: string
    /** When the live context (hub health, Jita guide) was captured. */
    context_as_of: string
    /** One-line verdict shown on the hub card and under the masthead. */
    headline: string
    opening: readonly string[]

    sales: MarketSalesTotals
    sales_vs: MarketSalesTotalsVs
    days: readonly MarketDayRow[]
    weeks: readonly MarketWeekRow[]
    weeks_dek: string
    categories: readonly MarketCategoryRow[]
    categories_dek: string

    top_types: {
        rows: readonly MarketTopTypeRow[]
        by_class: MarketTopTypesByClass
        dek: string
    }

    hulls: {
        rows: readonly MarketHullRow[]
        dek: string
        footnote: string
    }

    catchment: {
        amamake: MarketSystemSummary
        warzone: MarketWarzoneSummary
        rows: readonly MarketCatchmentRow[]
        regions: readonly MarketRegionRow[]
        pipe: MarketPipe
        dek: readonly string[]
        footnote: string
    }

    contracts: {
        totals: MarketContractTotals
        rows: readonly MarketContractHullRow[]
        dek: string
        footnote: string
    } | null

    margins: {
        rows: readonly MarketMarginRow[]
        dek: string
        footnote: string
        jita_as_of: string | null
    }

    import_vs_local: {
        dek: readonly string[]
        table: MarketTable
    }

    shelf: {
        dek: readonly string[]
        stats: readonly MarketStat[]
        actions: readonly MarketLink[]
    }

    get_involved: {
        steps: readonly MarketInvolvementStep[]
        actions: readonly MarketLink[]
        /** Guide slugs from the learning catalog, in display order. */
        featured_guides: readonly string[]
    }

    methodology: readonly MarketMethodologyEntry[]
}
