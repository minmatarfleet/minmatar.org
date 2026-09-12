#!/usr/bin/env node
/**
 * Authoritative data extractor for an Amamake Market Report issue.
 *
 * Two data feeds, one cached pass:
 *   - Sales: the my.minmatar.org API `GET /api/market/inferred-sales/monthly`
 *     (order-book-diff inferred fills at the Amamake freeport) for the target
 *     month and the prior month (deltas).
 *   - Destruction: the same per-system zKillboard cache the Warzone Report
 *     uses (`.cache/warzone/systems/`), for every Amarr–Minmatar FW system,
 *     so the two reports agree on every killmail count.
 *   - Live context: ESI `/industry/systems/` cost indices and the API's
 *     `/api/market/health` hub-health snapshot (both dated in the output).
 *
 * Type names, categories, capital classification and system→region come
 * from the local SDE sqlite (no API calls).
 *
 * Usage:
 *   node scripts/amamake_market_extract.mjs --year 2026 --month 8 --slug yc128-08 \
 *       [--api https://api.minmatar.org] [--top 10] [--hulls 8] [--systems 8] [--caps 6] \
 *       [--exclude 40520,40519] [--pipe Amamake,Auga,Siseide,Dal,Vard,Lantorn]
 *
 * Output: src/data/amamake-market/<slug>-boards.ts   (do not hand-edit; re-run instead)
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'

const args = Object.fromEntries(
    process.argv.slice(2).reduce((p, t, i, l) => (t.startsWith('--') && p.push([t.slice(2), l[i + 1]]), p), []),
)
const YEAR = Number(args.year)
const MONTH = Number(args.month)
const SLUG = args.slug
const API = (args.api ?? 'https://api.minmatar.org').replace(/\/$/, '')
const TOP = Number(args.top ?? 10)
const TOP_HULLS = Number(args.hulls ?? 8)
const TOP_SYSTEMS = Number(args.systems ?? 8)
const TOP_CAPS = Number(args.caps ?? 6)
const EXCLUDE_TYPE_IDS = new Set((args.exclude ?? '').split(',').filter(Boolean).map(Number))
const PIPE_SYSTEMS = (args.pipe ?? 'Amamake,Auga,Siseide,Dal,Vard,Lantorn').split(',').map((s) => s.trim())
if (!YEAR || !MONTH || !SLUG) {
    console.error('usage: node scripts/amamake_market_extract.mjs --year 2026 --month 8 --slug yc128-08 [--api URL]')
    process.exit(1)
}

const USER_AGENT = process.env.ZKILL_USER_AGENT ?? 'my.minmatar.org amamake-market-report script'
const LOCATION_ID = 1_022_167_642_188 // Amamake - 5 times nearly AT winners
const AMAMAKE_SYSTEM_ID = 30_002_537
const MILITIAS = { 500002: 'minmatar', 500003: 'amarr' }
const FRONT_BY_REGION = {
    Heimatar: 'Minmatar front',
    Metropolis: 'Minmatar front',
    Devoid: 'Amarr front',
    'The Bleak Lands': 'Amarr front',
}
const CAPSULES = new Set([670, 33328])
/** invGroups that count as "capital" for the capital-vs-subcap split. */
const CAPITAL_GROUPS = new Set([30, 485, 547, 659, 883, 902, 1538, 4594])
/** Systems whose industry cost indices the report quotes. */
const INDUSTRY_SYSTEMS = ['Amamake', 'Jita', 'Auner', 'Basgerin', 'Amo', 'Auga']

const ROOT = path.resolve(import.meta.dirname, '..')
const KILL_CACHE = path.join(ROOT, '.cache', 'warzone', 'systems')
const MARKET_CACHE = path.join(ROOT, '.cache', 'amamake-market')
const OUT_DIR = path.join(ROOT, 'src', 'data', 'amamake-market')
const OUT_FILE = path.join(OUT_DIR, `${SLUG}-boards.ts`)
const prev = MONTH === 1 ? { year: YEAR - 1, month: 12 } : { year: YEAR, month: MONTH - 1 }
const pad2 = (n) => String(n).padStart(2, '0')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const today = new Date()
const month_is_closed = new Date(Date.UTC(MONTH === 12 ? YEAR + 1 : YEAR, MONTH === 12 ? 0 : MONTH, 1)) <= today

async function fetch_json(url, attempt = 1) {
    const res = await fetch(url, { headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' } })
    if (res.status === 429 || res.status >= 500) {
        if (attempt > 6) throw new Error(`${url} failed (${res.status})`)
        await sleep(Math.min(60_000, 2_000 * 2 ** attempt))
        return fetch_json(url, attempt + 1)
    }
    if (!res.ok) throw new Error(`${url} -> ${res.status}`)
    return res.json()
}

/** Fetch-through JSON cache under .cache/amamake-market. */
async function cached_json(name, url, { cache = true } = {}) {
    const file = path.join(MARKET_CACHE, name)
    if (cache && existsSync(file)) return JSON.parse(await readFile(file, 'utf8'))
    const data = await fetch_json(url)
    if (cache) await writeFile(file, JSON.stringify(data))
    return data
}

/** Same on-disk layout as warzone_extract.mjs so both reports share one zKill pass. */
async function system_month_kills(sid, year, month) {
    const all = []
    let page = 1
    for (;;) {
        const file = path.join(KILL_CACHE, `${sid}-${year}-${pad2(month)}-${String(page).padStart(3, '0')}.json`)
        let rows
        if (existsSync(file)) {
            rows = JSON.parse(await readFile(file, 'utf8'))
        } else {
            rows = await fetch_json(`https://zkillboard.com/api/kills/systemID/${sid}/year/${year}/month/${month}/page/${page}/`)
            await writeFile(file, JSON.stringify(rows))
            await sleep(1_100)
        }
        if (!Array.isArray(rows) || rows.length === 0) break
        all.push(...rows)
        if (rows.length < 200) break
        page += 1
    }
    return all
}

const clean = (rows, year, month) => {
    const prefix = `${year}-${pad2(month)}`
    return rows.filter((k) => k.killmail_time?.startsWith(prefix) && !k.zkb?.npc && !CAPSULES.has(k.victim?.ship_type_id))
}

const fmt_isk = (v) => {
    if (v >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(2)}T`
    if (v >= 100_000_000_000) return `${Math.round(v / 1_000_000_000)}B`
    if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(0)}M`
    return `${(v / 1_000).toFixed(0)}k`
}
const round1 = (v) => Math.round(v * 10) / 10
const pct_change = (now, before) => (before > 0 ? Math.round(((now - before) / before) * 100) : null)
const by = (key) => (a, b) => b[key] - a[key]

await mkdir(KILL_CACHE, { recursive: true })
await mkdir(MARKET_CACHE, { recursive: true })
await mkdir(OUT_DIR, { recursive: true })

// ---------------------------------------------------------------- SDE lookups
const sde = new Database(path.join(ROOT, 'src', 'data', 'sde-3316380.sqlite'), { readonly: true })
const type_row = sde.prepare(`
    SELECT t.typeName AS name, t.groupID AS group_id, g.groupName AS group_name, c.categoryName AS category
    FROM invTypes t
    JOIN invGroups g ON g.groupID = t.groupID
    JOIN invCategories c ON c.categoryID = g.categoryID
    WHERE t.typeID = ?`)
const type_cache = new Map()
const type_meta = (tid) => {
    if (!type_cache.has(tid)) type_cache.set(tid, type_row.get(tid) ?? { name: `Type ${tid}`, group_id: 0, group_name: '', category: '' })
    return type_cache.get(tid)
}
const is_capital = (tid) => CAPITAL_GROUPS.has(type_meta(tid).group_id)
const sys_row = sde.prepare(`
    SELECT s.solarSystemID AS id, s.solarSystemName AS name, r.regionName AS region
    FROM mapSolarSystems s JOIN mapRegions r ON r.regionID = s.regionID
    WHERE s.solarSystemID = ?`)
const sys_by_name = sde.prepare(`SELECT solarSystemID AS id FROM mapSolarSystems WHERE solarSystemName = ?`)
const sys_meta = (sid) => sys_row.get(sid) ?? { id: sid, name: String(sid), region: '' }

// ---------------------------------------------------------------- Sales feed
async function monthly_sales(year, month) {
    const closed = new Date(Date.UTC(month === 12 ? year + 1 : year, month === 12 ? 0 : month, 1)) <= today
    return cached_json(
        `sales-${LOCATION_ID}-${year}-${pad2(month)}.json`,
        `${API}/api/market/inferred-sales/monthly?location_id=${LOCATION_ID}&year=${year}&month=${month}`,
        { cache: closed },
    )
}
console.error(`sales: ${API} · ${YEAR}-${pad2(MONTH)} (+ ${prev.year}-${pad2(prev.month)} for deltas)`)
const sales = await monthly_sales(YEAR, MONTH)
const sales_prev = await monthly_sales(prev.year, prev.month)
const prev_by_type = new Map(sales_prev.by_type.map((t) => [t.type_id, t]))
console.error(`sales: ${sales.totals.fills} fills · ${fmt_isk(sales.totals.isk)} · ${sales.totals.types} types`)

// Weekly buckets on day-of-month: 1–7, 8–14, 15–21, 22–28, 29–end.
const days_in_month = new Date(Date.UTC(YEAR, MONTH, 0)).getUTCDate()
const month_short = new Date(Date.UTC(YEAR, MONTH - 1, 1)).toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })
const week_bounds = [[1, 7], [8, 14], [15, 21], [22, 28], [29, days_in_month]].filter(([lo]) => lo <= days_in_month)
const WEEKS = week_bounds.map(([lo, hi], i) => ({
    label: i === 0 ? `${lo}–${hi} ${month_short}` : `${lo}–${hi}`,
    isk: 0,
    fills: 0,
    units: 0,
}))
const DAYS = sales.days.map((d) => ({ date: d.date, isk: d.isk, fills: d.fills, units: d.units }))
for (const d of sales.days) {
    const dom = Number(d.date.slice(8, 10))
    const idx = week_bounds.findIndex(([lo, hi]) => dom >= lo && dom <= hi)
    if (idx >= 0) {
        WEEKS[idx].isk += d.isk
        WEEKS[idx].fills += d.fills
        WEEKS[idx].units += d.units
    }
}
const loudest_sales_day = [...sales.days].sort(by('isk'))[0] ?? null
const quietest_sales_day = [...sales.days].sort((a, b) => a.isk - b.isk)[0] ?? null

// Category buckets (SDE category → report bucket).
const bucket_for_type = (t) => {
    const meta = type_meta(t.type_id)
    const category = meta.category || t.category
    const group = meta.group_name || t.group
    if (category === 'Ship') return 'Ships'
    if (category === 'Module' || category === 'Subsystem') return 'Modules'
    if (category === 'Charge') return 'Charges'
    if (category === 'Drone' || category === 'Fighter') return 'Drones'
    if (group === 'Skill Injectors' || category === 'Implant') return 'Injectors & implants'
    if (category === 'Blueprint') return 'Blueprints'
    if (['Material', 'Commodity', 'Planetary Resources', 'Planetary Commodities', 'Asteroid', 'Reaction Materials'].includes(category)) return 'Materials & commodities'
    return 'Other'
}
const bucket_totals = (rows) => {
    const out = new Map()
    for (const t of rows) {
        const b = bucket_for_type(t)
        const cur = out.get(b) ?? { name: b, isk: 0, units: 0, fills: 0 }
        cur.isk += t.isk
        cur.units += t.units
        cur.fills += t.fills
        out.set(b, cur)
    }
    return out
}
const buckets_now = bucket_totals(sales.by_type)
const buckets_prev = bucket_totals(sales_prev.by_type)
const CATEGORIES = [...buckets_now.values()]
    .sort(by('isk'))
    .map((b) => ({
        ...b,
        isk_label: fmt_isk(b.isk),
        share: round1((b.isk / Math.max(sales.totals.isk, 1)) * 100),
        isk_vs: b.isk - (buckets_prev.get(b.name)?.isk ?? 0),
        isk_vs_pct: pct_change(b.isk, buckets_prev.get(b.name)?.isk ?? 0),
    }))

// Top types by inferred ISK (editorial exclusions via --exclude).
const TOP_TYPES = sales.by_type
    .filter((t) => !EXCLUDE_TYPE_IDS.has(t.type_id))
    .sort(by('isk'))
    .slice(0, TOP)
    .map((t) => {
        const p = prev_by_type.get(t.type_id)
        return {
            typeId: t.type_id,
            name: type_meta(t.type_id).name || t.name,
            category: bucket_for_type(t),
            isk: t.isk,
            isk_label: fmt_isk(t.isk),
            units: t.units,
            fills: t.fills,
            share: round1((t.isk / Math.max(sales.totals.isk, 1)) * 100),
            isk_vs_pct: p ? pct_change(t.isk, p.isk) : null,
            is_new: !p,
        }
    })

// ---------------------------------------------------------------- Destruction feed
const fw = await fetch_json('https://esi.evetech.net/latest/fw/systems/')
const wz = fw.filter((s) => [500002, 500003].includes(s.owner_faction_id))
const holder = new Map(wz.map((s) => [s.solar_system_id, MILITIAS[s.occupier_faction_id] ?? MILITIAS[s.owner_faction_id]]))
const system_ids = wz.map((s) => s.solar_system_id)
if (!system_ids.includes(AMAMAKE_SYSTEM_ID)) system_ids.push(AMAMAKE_SYSTEM_ID)
console.error(`kills: ${system_ids.length} FW systems from ESI · cache ${KILL_CACHE}`)

const system_stats = new Map() // sid -> {ships, isk, capital_isk, capital_ships, ships_prev, isk_prev}
let amamake_kills = []
let amamake_kills_prev = []
const unique_chars = new Set()
let done = 0
for (const sid of system_ids) {
    const now = clean(await system_month_kills(sid, YEAR, MONTH), YEAR, MONTH)
    const before = clean(await system_month_kills(sid, prev.year, prev.month), prev.year, prev.month)
    const stat = { ships: now.length, isk: 0, capital_isk: 0, capital_ships: 0, ships_prev: before.length, isk_prev: 0 }
    for (const k of now) {
        const v = k.zkb?.totalValue ?? 0
        stat.isk += v
        if (is_capital(k.victim?.ship_type_id)) {
            stat.capital_isk += v
            stat.capital_ships += 1
        }
    }
    for (const k of before) stat.isk_prev += k.zkb?.totalValue ?? 0
    system_stats.set(sid, stat)
    if (sid === AMAMAKE_SYSTEM_ID) {
        amamake_kills = now
        amamake_kills_prev = before
        for (const k of now) {
            if (k.victim?.character_id) unique_chars.add(k.victim.character_id)
            for (const a of k.attackers ?? []) if (a.character_id) unique_chars.add(a.character_id)
        }
    }
    done += 1
    if (done % 10 === 0) console.error(`kills: ${done}/${system_ids.length} systems`)
}

const warzone_ships = [...system_stats.values()].reduce((s, r) => s + r.ships, 0)
const warzone_isk = [...system_stats.values()].reduce((s, r) => s + r.isk, 0)
const warzone_ships_prev = [...system_stats.values()].reduce((s, r) => s + r.ships_prev, 0)
const warzone_isk_prev = [...system_stats.values()].reduce((s, r) => s + r.isk_prev, 0)

const catchment_all = system_ids.map((sid) => {
    const meta = sys_meta(sid)
    const stat = system_stats.get(sid)
    return {
        system: meta.name,
        system_id: sid,
        region: meta.region,
        front: FRONT_BY_REGION[meta.region] ?? meta.region,
        href: `https://zkillboard.com/system/${sid}/`,
        ships: stat.ships,
        ships_vs: stat.ships - stat.ships_prev,
        isk: stat.isk,
        isk_label: fmt_isk(stat.isk),
        isk_vs: stat.isk - stat.isk_prev,
        capital_ships: stat.capital_ships,
        capital_isk: stat.capital_isk,
        capital_share: round1((stat.capital_isk / Math.max(stat.isk, 1)) * 100),
        share_of_warzone: round1((stat.ships / Math.max(warzone_ships, 1)) * 100),
        holds_today: holder.get(sid) ?? 'minmatar',
    }
})
const CATCHMENT = [...catchment_all].sort(by('ships')).slice(0, TOP_SYSTEMS)
const CAPITAL_SPLIT = [...catchment_all]
    .sort(by('capital_isk'))
    .slice(0, TOP_CAPS)
    .map((r) => ({
        system: r.system,
        system_id: r.system_id,
        capital_ships: r.capital_ships,
        capital_isk: r.capital_isk,
        subcap_isk: r.isk - r.capital_isk,
        capital_isk_label: fmt_isk(r.capital_isk),
        subcap_isk_label: fmt_isk(r.isk - r.capital_isk),
    }))

const region_totals = new Map()
for (const r of catchment_all) {
    const cur = region_totals.get(r.region) ?? { region: r.region, front: r.front, ships: 0, isk: 0 }
    cur.ships += r.ships
    cur.isk += r.isk
    region_totals.set(r.region, cur)
}
const REGIONS = [...region_totals.values()]
    .sort(by('ships'))
    .map((r) => ({ ...r, isk_label: fmt_isk(r.isk), share: round1((r.ships / Math.max(warzone_ships, 1)) * 100) }))

const pipe_rows = catchment_all.filter((r) => PIPE_SYSTEMS.includes(r.system))
const pipe_ships = pipe_rows.reduce((s, r) => s + r.ships, 0)
const PIPE = {
    label: PIPE_SYSTEMS.join(', '),
    systems: PIPE_SYSTEMS,
    ships: pipe_ships,
    isk: pipe_rows.reduce((s, r) => s + r.isk, 0),
    share: round1((pipe_ships / Math.max(warzone_ships, 1)) * 100),
}

const amamake_stat = system_stats.get(AMAMAKE_SYSTEM_ID)
const day_counts = new Map()
for (const k of amamake_kills) {
    const d = k.killmail_time.slice(0, 10)
    day_counts.set(d, (day_counts.get(d) ?? 0) + 1)
}
const loudest_kill_day = [...day_counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? ['', 0]
const AMAMAKE = {
    system_id: AMAMAKE_SYSTEM_ID,
    ships: amamake_stat.ships,
    ships_vs: amamake_stat.ships - amamake_stat.ships_prev,
    isk: amamake_stat.isk,
    isk_label: fmt_isk(amamake_stat.isk),
    isk_vs: amamake_stat.isk - amamake_stat.isk_prev,
    share_of_warzone: round1((amamake_stat.ships / Math.max(warzone_ships, 1)) * 100),
    unique_characters: unique_chars.size,
    capital_ships: amamake_stat.capital_ships,
    capital_isk: amamake_stat.capital_isk,
    loudest_day: { date: loudest_kill_day[0], ships: loudest_kill_day[1] },
    holds_today: holder.get(AMAMAKE_SYSTEM_ID) ?? 'minmatar',
}
const WARZONE = {
    systems: system_ids.length,
    ships: warzone_ships,
    ships_vs: warzone_ships - warzone_ships_prev,
    isk: warzone_isk,
    isk_label: fmt_isk(warzone_isk),
    isk_vs: warzone_isk - warzone_isk_prev,
}

// Died vs sold: hulls lost in Amamake vs inferred sells of the same hull.
const lost_by_type = (rows) => {
    const out = new Map()
    for (const k of rows) out.set(k.victim.ship_type_id, (out.get(k.victim.ship_type_id) ?? 0) + 1)
    return out
}
const lost_now = lost_by_type(amamake_kills)
const lost_prev = lost_by_type(amamake_kills_prev)
const sold_by_type = new Map(sales.by_type.map((t) => [t.type_id, t.units]))
const hull_ids = new Set([...lost_now.keys(), ...sales.by_type.filter((t) => type_meta(t.type_id).category === 'Ship').map((t) => t.type_id)])
const HULLS = [...hull_ids]
    .filter((tid) => type_meta(tid).category === 'Ship' && !EXCLUDE_TYPE_IDS.has(tid))
    .map((tid) => {
        const sold = sold_by_type.get(tid) ?? 0
        const lost = lost_now.get(tid) ?? 0
        return {
            typeId: tid,
            name: type_meta(tid).name,
            group: type_meta(tid).group_name,
            sold,
            lost,
            sold_vs: sold - (prev_by_type.get(tid)?.units ?? 0),
            lost_vs: lost - (lost_prev.get(tid) ?? 0),
            ratio: lost > 0 ? round1(sold / lost) : null,
        }
    })
    .sort((a, b) => b.sold + b.lost - (a.sold + a.lost))
const HULLS_TOP = HULLS.slice(0, TOP_HULLS)
const hulls_sold_total = HULLS.reduce((s, h) => s + h.sold, 0)
const hulls_lost_total = HULLS.reduce((s, h) => s + h.lost, 0)

// ---------------------------------------------------------------- Live context
const industry_all = await cached_json(`industry-${today.toISOString().slice(0, 10)}.json`, 'https://esi.evetech.net/latest/industry/systems/')
const industry_by_id = new Map(industry_all.map((r) => [r.solar_system_id, r]))
const INDUSTRY_INDICES = INDUSTRY_SYSTEMS.map((name) => {
    const id = sys_by_name.get(name)?.id
    const row = id ? industry_by_id.get(id) : undefined
    const idx = (activity) => row?.cost_indices?.find((c) => c.activity === activity)?.cost_index ?? null
    return { system: name, system_id: id ?? 0, manufacturing: idx('manufacturing'), reaction: idx('reaction') }
})

let HUB_HEALTH = null
try {
    const health = await fetch_json(`${API}/api/market/health?location_id=${LOCATION_ID}&days=1`)
    const sell = health.sell_orders?.latest ?? null
    const contracts = health.contracts?.latest ?? null
    HUB_HEALTH = {
        sell_orders_health_pct: sell?.health_pct ?? null,
        sell_orders_viability_pct: sell?.viability_pct ?? null,
        sell_orders_isk: sell?.isk ?? null,
        contracts_health_pct: contracts?.health_pct ?? null,
        contracts_isk: contracts?.isk ?? null,
        synced_at: sell?.synced_at ?? contracts?.synced_at ?? null,
    }
} catch (error) {
    console.error(`hub health: unavailable (${error.message})`)
}

// ---------------------------------------------------------------- Output
const sales_vs = {
    isk: sales.totals.isk - sales_prev.totals.isk,
    isk_pct: pct_change(sales.totals.isk, sales_prev.totals.isk),
    fills: sales.totals.fills - sales_prev.totals.fills,
    fills_pct: pct_change(sales.totals.fills, sales_prev.totals.fills),
    units: sales.totals.units - sales_prev.totals.units,
    units_pct: pct_change(sales.totals.units, sales_prev.totals.units),
    types: sales.totals.types - sales_prev.totals.types,
}

const ts = (name, type, value) => `export const ${name}: ${type} = ${JSON.stringify(value, null, 4)}\n`
const out = [
    `// Generated by scripts/amamake_market_extract.mjs — do not hand-edit; re-run instead.`,
    `// node scripts/amamake_market_extract.mjs --year ${YEAR} --month ${MONTH} --slug ${SLUG}`,
    `// Sales: ${API} inferred-sales/monthly · Kills: zKillboard per-system cache · Extracted ${today.toISOString()}`,
    ``,
    `import type {`,
    `    MarketCapitalSplitRow,`,
    `    MarketCatchmentRow,`,
    `    MarketCategoryRow,`,
    `    MarketDayRow,`,
    `    MarketHubHealth,`,
    `    MarketHullRow,`,
    `    MarketIndustryIndexRow,`,
    `    MarketPipe,`,
    `    MarketRegionRow,`,
    `    MarketSalesTotals,`,
    `    MarketSalesTotalsVs,`,
    `    MarketSystemSummary,`,
    `    MarketTopTypeRow,`,
    `    MarketWarzoneSummary,`,
    `    MarketWeekRow,`,
    `} from './types'`,
    ``,
    `export const EXTRACTED_AT = ${JSON.stringify(today.toISOString())}`,
    `export const MONTH_IS_CLOSED = ${month_is_closed}`,
    `export const LOCATION_ID = ${LOCATION_ID}`,
    `export const DAYS_IN_MONTH = ${days_in_month}`,
    ``,
    ts('SALES_TOTALS', 'MarketSalesTotals', {
        isk: sales.totals.isk,
        isk_label: fmt_isk(sales.totals.isk),
        fills: sales.totals.fills,
        units: sales.totals.units,
        types: sales.totals.types,
        days_with_sales: sales.days.length,
        loudest_day: loudest_sales_day ? { date: loudest_sales_day.date, isk: loudest_sales_day.isk, fills: loudest_sales_day.fills } : null,
        quietest_day: quietest_sales_day ? { date: quietest_sales_day.date, isk: quietest_sales_day.isk, fills: quietest_sales_day.fills } : null,
    }),
    ts('SALES_TOTALS_PREV', 'MarketSalesTotals', {
        isk: sales_prev.totals.isk,
        isk_label: fmt_isk(sales_prev.totals.isk),
        fills: sales_prev.totals.fills,
        units: sales_prev.totals.units,
        types: sales_prev.totals.types,
        days_with_sales: sales_prev.days.length,
        loudest_day: null,
        quietest_day: null,
    }),
    ts('SALES_TOTALS_VS', 'MarketSalesTotalsVs', sales_vs),
    ts('DAYS', 'readonly MarketDayRow[]', DAYS),
    ts('WEEKS', 'readonly MarketWeekRow[]', WEEKS.map((w) => ({ ...w, isk_label: fmt_isk(w.isk) }))),
    ts('CATEGORIES', 'readonly MarketCategoryRow[]', CATEGORIES),
    ts('TOP_TYPES', 'readonly MarketTopTypeRow[]', TOP_TYPES),
    ts('HULLS', 'readonly MarketHullRow[]', HULLS_TOP),
    `export const HULLS_SOLD_TOTAL = ${hulls_sold_total}`,
    `export const HULLS_LOST_TOTAL = ${hulls_lost_total}`,
    ts('AMAMAKE', 'MarketSystemSummary', AMAMAKE),
    ts('WARZONE', 'MarketWarzoneSummary', WARZONE),
    ts('CATCHMENT', 'readonly MarketCatchmentRow[]', CATCHMENT),
    ts('REGIONS', 'readonly MarketRegionRow[]', REGIONS),
    ts('PIPE', 'MarketPipe', PIPE),
    ts('CAPITAL_SPLIT', 'readonly MarketCapitalSplitRow[]', CAPITAL_SPLIT),
    ts('INDUSTRY_INDICES', 'readonly MarketIndustryIndexRow[]', INDUSTRY_INDICES),
    `export const INDUSTRY_AS_OF = ${JSON.stringify(today.toISOString().slice(0, 10))}`,
    ts('HUB_HEALTH', 'MarketHubHealth | null', HUB_HEALTH),
].join('\n')

await writeFile(OUT_FILE, out)
console.error(`wrote ${path.relative(ROOT, OUT_FILE)}`)
console.error(`  sales ${fmt_isk(sales.totals.isk)} (${sales_vs.isk_pct ?? '—'}% vs prior) · ${sales.totals.fills} fills · ${sales.totals.units} units`)
console.error(`  Amamake ${AMAMAKE.ships} ships (${AMAMAKE.share_of_warzone}% of ${WARZONE.ships}) · ${AMAMAKE.isk_label} · ${AMAMAKE.unique_characters} characters`)
console.error(`  top type ${TOP_TYPES[0]?.name} ${TOP_TYPES[0]?.isk_label} · top hull ${HULLS_TOP[0]?.name} ${HULLS_TOP[0]?.sold} sold / ${HULLS_TOP[0]?.lost} lost`)
