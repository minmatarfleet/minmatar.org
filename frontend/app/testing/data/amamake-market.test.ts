import { describe, expect, it } from 'vitest'

import {
    format_markup_pct,
    get_adjacent_issues,
    get_issue,
    get_issue_slugs,
    get_latest_issue,
    get_sold_class_names,
    ISSUES,
    issue_label,
    resolve_sold_types,
    SOLD_CLASS_ALL,
    sold_class_slug,
} from '@/data/amamake-market'
import { campaigns, getAllCampaigns, getWarzoneReports } from '@/data/campaigns'
import { defaultLang, ui } from '@i18n/ui'

describe('amamake market issue registry', () => {
    it('lists yc128-08 as the latest issue', () => {
        expect(get_latest_issue().slug).toBe('yc128-08')
        expect(get_issue('yc128-08')?.permalink_path).toBe('/amamake-market/yc128-08/')
        expect(get_issue_slugs()).toContain('yc128-08')
        expect(ISSUES).toHaveLength(1)
        expect(issue_label(get_latest_issue())).toBe('August YC128')
    })

    it('returns undefined for an unknown slug', () => {
        expect(get_issue('yc128-99')).toBeUndefined()
        expect(get_adjacent_issues('yc128-99')).toEqual({})
    })

    it('wires the generated sales totals into the issue', () => {
        const issue = get_latest_issue()
        expect(issue.sales.isk).toBeGreaterThan(0)
        expect(issue.sales.fills).toBeGreaterThan(0)
        expect(issue.sales.profit_types).toBeGreaterThan(0)
        expect(typeof issue.sales.profit).toBe('number')
        expect(issue.sales.profit_label).toBeTruthy()
        expect(issue.weeks.length).toBeGreaterThan(3)
        expect(issue.catchment.rows[0]?.system).toBe('Amamake')
        expect(issue.hulls.rows.length).toBeGreaterThan(0)
        expect(issue.hulls.dek).toMatch(/sold here versus what died/)
        expect(issue.methodology.some((entry) => entry.label === 'Destruction')).toBe(true)
        expect(issue).not.toHaveProperty('focus')
        expect(issue).not.toHaveProperty('focus_name')
        expect(issue).not.toHaveProperty('industry')
        expect(issue).not.toHaveProperty('loyalty')
        expect(issue.catchment.amamake.ships).toBeGreaterThan(0)
    })

    it('uses a complete production month of inferred sales', () => {
        const issue = get_latest_issue()
        expect(issue.days).toHaveLength(31)
        expect(issue.sales.days_with_sales).toBe(31)
        expect(issue.days.every((day) => day.isk > 0)).toBe(true)
    })

    it('compares Amamake sells to warzone-wide hull losses', () => {
        const issue = get_latest_issue()
        const lost = issue.hulls.rows.reduce((sum, row) => sum + row.lost, 0)
        expect(issue.catchment.warzone.ships).toBeGreaterThan(issue.catchment.amamake.ships)
        expect(lost).toBeGreaterThan(issue.catchment.amamake.ships)
        expect(issue.hulls.dek).toMatch(/sold here versus what died/)
    })

    it('has sell-order class totals with month-over-month', () => {
        const issue = get_latest_issue()
        const names = issue.categories.map((row) => row.name)
        expect(names).toEqual(expect.arrayContaining(['Ships', 'Modules', 'Rigs', 'Charges', 'Drones']))
        expect(names).not.toContain('Blueprints')
        expect(issue.categories.every((row) => typeof row.isk_vs === 'number')).toBe(true)
    })

    it('records volume-weighted markup versus Jita on types and classes', () => {
        const issue = get_latest_issue()
        expect(format_markup_pct(null)).toBe('—')
        expect(format_markup_pct(12.5)).toBe('+12.5%')
        expect(format_markup_pct(-4)).toBe('-4%')
        expect(format_markup_pct(0)).toBe('0%')
        expect(issue.top_types.rows.some((row) => row.markup_pct !== null)).toBe(true)
        expect(issue.categories.some((row) => row.markup_pct !== null)).toBe(true)
        for (const row of issue.top_types.rows) {
            expect(row.markup_pct === null || typeof row.markup_pct === 'number').toBe(true)
        }
        for (const row of issue.categories) {
            expect(row.markup_pct === null || typeof row.markup_pct === 'number').toBe(true)
        }
        const missing = issue.top_types.rows.filter((row) => row.markup_pct === null)
        expect(missing.every((row) => format_markup_pct(row.markup_pct) === '—')).toBe(true)
    })

    it('computes inferred profit net of Jita plus Jita→Amamake freight', () => {
        const issue = get_latest_issue()
        expect(issue.sales.profit_types + issue.sales.profit_unpriced_types).toBeLessThanOrEqual(issue.sales.types)
        expect(issue.sales.profit_unpriced_types).toBeGreaterThanOrEqual(0)
        expect(issue.sales.profit).not.toBe(issue.sales.isk)
        expect(typeof issue.sales_vs.profit).toBe('number')
        const profit_entry = issue.methodology.find((entry) => entry.label === 'Profit')
        expect(profit_entry?.text).toMatch(/Amamake fill average/)
        expect(profit_entry?.text).toMatch(/450 ISK\/m³/)
        expect(profit_entry?.text).toMatch(/Jita → Amamake/)
        expect(profit_entry?.text).toMatch(/excluded from the total/)
        expect(profit_entry?.text).toContain(issue.sales.profit_label)
    })

    it('resolves What sold class chips to that class top ten', () => {
        const issue = get_latest_issue()
        expect(sold_class_slug('PLEX adjacent')).toBe('plex-adjacent')
        expect(sold_class_slug('Materials & commodities')).toBe('materials-commodities')
        expect(get_sold_class_names(issue)).toContain('Ships')
        expect(get_sold_class_names(issue)).toContain('PLEX adjacent')
        expect(get_sold_class_names(issue)).not.toContain('Blueprints')
        expect(get_sold_class_names(issue)).not.toContain('Consumables')
        expect(get_sold_class_names(issue)).not.toContain('Gas')
        expect(resolve_sold_types(issue, SOLD_CLASS_ALL).rows).toEqual(issue.top_types.rows)
        const ships = resolve_sold_types(issue, 'ships')
        expect(ships.class_name).toBe('Ships')
        expect(ships.rows.every((row) => row.category === 'Ships')).toBe(true)
        expect(resolve_sold_types(issue, 'not-a-class').slug).toBe(SOLD_CLASS_ALL)
    })

    it('groups injectors, extractors, and PLEX as PLEX adjacent', () => {
        const issue = get_latest_issue()
        const plex = resolve_sold_types(issue, 'plex-adjacent')
        const names = plex.rows.map((row) => row.name)
        expect(plex.class_name).toBe('PLEX adjacent')
        expect(names).toEqual(
            expect.arrayContaining(['Large Skill Injector', 'Small Skill Injector', 'Skill Extractor']),
        )
        expect(plex.rows.every((row) => row.category === 'PLEX adjacent')).toBe(true)
        expect(names).not.toContain('Nanite Repair Paste')
        const other = resolve_sold_types(issue, 'other')
        const other_names = other.rows.map((row) => row.name)
        expect(other_names).not.toContain('Large Skill Injector')
        expect(other_names).not.toContain('Small Skill Injector')
        expect(other_names).not.toContain('Skill Extractor')
        expect(other_names).not.toContain('Magmatic Gas')
        expect(other_names).not.toContain('Rorqual Blueprint')
        expect(other_names).not.toContain('Loki Hrada-Oki Offender SKIN')
        expect(other_names).toContain('Mobile Cynosural Beacon')
        expect(other.rows.every((row) => row.category === 'Other')).toBe(true)
        const materials = resolve_sold_types(issue, 'materials-commodities')
        expect(materials.class_name).toBe('Materials & commodities')
        expect(materials.rows.every((row) => row.category === 'Materials & commodities')).toBe(true)
        expect(Object.keys(issue.top_types.by_class)).not.toContain('Blueprints')
        expect(Object.keys(issue.top_types.by_class)).not.toContain('Gas')
    })

    it('has a top-10 inferred-ISK board for each sell-order class', () => {
        const issue = get_latest_issue()
        const ships = issue.top_types.by_class['Ships'] ?? []
        expect(issue.top_types.rows).toHaveLength(10)
        expect(ships.length).toBeGreaterThan(0)
        expect(ships.length).toBeLessThanOrEqual(10)
        expect(ships.every((row) => row.category === 'Ships')).toBe(true)
        expect(ships[0]!.isk).toBeGreaterThanOrEqual(ships[ships.length - 1]!.isk)
        expect(Object.keys(issue.top_types.by_class)).toEqual(
            expect.arrayContaining(['Ships', 'Modules', 'Rigs', 'Charges', 'Drones']),
        )
    })

    it('ranks high-volume good-margin plays by extra ISK', () => {
        const rows = get_latest_issue().margins.rows
        expect(rows.length).toBeGreaterThan(0)
        for (let index = 1; index < rows.length; index++) {
            expect(rows[index - 1]!.extra_isk).toBeGreaterThanOrEqual(rows[index]!.extra_isk)
        }
        expect(rows.every((row) => row.fills >= 25)).toBe(true)
        expect(rows.every((row) => row.units >= 25)).toBe(true)
        expect(rows.every((row) => row.margin_pct >= 5)).toBe(true)
    })

    it('describes All Items Sold as an API-backed paginated catalog', () => {
        const { volume, methodology } = get_latest_issue()
        expect(volume.dek).toContain('Everything that moved')
        expect(volume.location_id).toBeGreaterThan(0)
        expect(volume.year).toBe(2026)
        expect(volume.month).toBe(8)
        expect(methodology.some((entry) => entry.label === 'All Items Sold')).toBe(true)
        expect(
            methodology.find((entry) => entry.label === 'All Items Sold')!.text,
        ).toContain('5 per page')
        expect(
            methodology.find((entry) => entry.label === 'All Items Sold')!.text,
        ).toContain('browse budget')
    })

    it('has a three-step get-involved loop with freight and market ops', () => {
        const { get_involved } = get_latest_issue()
        expect(get_involved.steps).toHaveLength(3)
        expect(get_involved.steps.map((step) => step.title)).toEqual([
            'Find the holes',
            'Haul it in',
            'List it',
        ])
        expect(get_involved.steps[0]!.href).toBe('/market/ops/sell_orders/')
        expect(get_involved.steps[0]!.text).toContain('All Items Sold')
        expect(get_involved.steps[1]!.href).toBe('/market/freight/calculator/')
        expect(get_involved.steps[1]!.text).toContain('450 ISK/m³')
        expect(get_involved.dek).toContain('PushX')
        expect(get_involved.actions.map((link) => link.href)).toEqual([
            '/market/freight/calculator/',
            '/market/ops/sell_orders/',
        ])
    })

    it('never publishes Type {id} fallback names for live market types', () => {
        const issue = get_latest_issue()
        const rows = [
            ...issue.top_types.rows,
            ...Object.values(issue.top_types.by_class).flat(),
            ...issue.hulls.rows,
            ...issue.margins.rows,
        ]
        const names = rows.map((row) => row.name)
        expect(names.every((name) => Boolean(name) && !/^Type \d+$/.test(name))).toBe(true)
        expect(issue.top_types.by_class['Drones']?.map((row) => row.name)).toContain('Inshore EC-300-I')
        expect(issue.top_types.by_class['Other']?.map((row) => row.name) ?? []).not.toContain(
            'Loki Hrada-Oki Offender SKIN',
        )
        expect(issue.top_types.by_class['Other']?.map((row) => row.name) ?? []).not.toContain('Rorqual Blueprint')
    })
})

describe('amamake market content-hub registration', () => {
    it('lists the August issue as a warzone economic report on its permalink', () => {
        const entry = campaigns.find((campaign) => campaign.slug === 'amamake-market-yc128-08')

        expect(entry).toBeDefined()
        expect(entry).toMatchObject({
            kind: 'warzone',
            warzone_type: 'economic',
            path: '/amamake-market/yc128-08/',
            isk_label_key: 'sold',
        })
        expect(entry?.iskDestroyed).toBe(get_latest_issue().sales.isk)
        expect(getWarzoneReports().some((report) => report.slug === 'amamake-market-yc128-08')).toBe(true)
    })

    it('keeps economic reports out of the campaigns strip', () => {
        expect(getAllCampaigns().some((campaign) => campaign.slug === 'amamake-market-yc128-08')).toBe(false)
    })

    it('labels the series Amamake Economic Report', () => {
        const copy = ui[defaultLang]
        expect(copy['content.kind.warzone.economic']).toBe('Amamake Economic Report')
        expect(copy['amamake_market.yc128_08.name']).toBe('Amamake Economic Report · August YC128')
        expect(copy['amamake_market.yc128_08.page_title']).toBe('Amamake Economic Report · August YC128')
        expect(copy['amamake_market.page_title']).toBe('Amamake Economic Report')
        expect(copy['content.kind.warzone.frontline']).toBe('Frontline Report')
    })
})
