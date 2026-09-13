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
 *     so the two reports agree on every killmail count. Died vs sold matches
 *     inferred Amamake sells to hulls lost across that whole warzone.
 *   - Live context: the API's `/api/market/health` hub-health snapshot
 *     (dated in the output). Finished contracts and Forge Jita averages
 *     come from the production_readonly cache dump when present.
 *
 * Type names, categories, capital classification and system→region come
 * from the local SDE sqlite first, then inferred-sales payload names, then
 * ESI (`POST /universe/names/` and `GET /universe/types/{id}/`) so types
 * newer than the bundled SDE never publish as "Type {id}".
 *
 * Usage:
 *   node scripts/amamake_market_extract.mjs --year 2026 --month 8 --slug yc128-08 \
 *       [--api https://api.minmatar.org] [--top 10] [--hulls 8] [--systems 8] [--caps 6] \
 *       [--exclude 40520,40519] [--pipe Amamake,Auga,Siseide,Dal,Vard,Lantorn]
 *
 * Output: src/data/amamake-market/<slug>-boards.ts   (do not hand-edit; re-run instead)
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync, statSync } from 'node:fs'
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
/**
 * Alliance freight calculator: active EveFreightRoute Jita → Amamake (Heimatar
 * pipe), rate type. Volume charge only (ISK/m³ × packaged m³). Collateral % is
 * not applied — inferred fills have no collateral.
 */
const FREIGHT_ISK_PER_M3 = 450
const FREIGHT_ROUTE_LABEL = 'Jita → Amamake'
/** Skill Injectors (1739) + PLEX (1875). Extractor / MPT live in Services — type-id only. */
const PLEX_ADJACENT_GROUPS = new Set(['Skill Injectors', 'PLEX'])
const PLEX_ADJACENT_TYPE_IDS = new Set([
    40519, // Skill Extractor
    63188, // Multiple Pilot Training
    34133, // Multiple Pilot Training Certificate
    29668, // 30 Day Pilot's License Extension (PLEX)
])
const MATERIAL_CATEGORIES = new Set([
    'Material', 'Commodity', 'Planetary Resources', 'Planetary Commodities',
    'Asteroid', 'Reaction Materials', 'Colony Resources',
    'Gas', 'Fullerite', 'Booster Gas',
])
const MATERIAL_GROUPS = new Set([
    'Harvestable Cloud', 'Compressed Gas', 'Colony Reagents', 'Fullerite', 'Booster Gas',
])

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

async function fetch_json(url, init = {}, attempt = 1) {
    const res = await fetch(url, {
        ...init,
        headers: { 'User-Agent': USER_AGENT, Accept: 'application/json', ...(init.headers ?? {}) },
    })
    if (res.status === 429 || res.status >= 500) {
        if (attempt > 6) throw new Error(`${url} failed (${res.status})`)
        await sleep(Math.min(60_000, 2_000 * 2 ** attempt))
        return fetch_json(url, init, attempt + 1)
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

async function read_cache_json(name) {
    const file = path.join(MARKET_CACHE, name)
    if (!existsSync(file)) return null
    return JSON.parse(await readFile(file, 'utf8'))
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
    const mag = Math.abs(v)
    const body = mag >= 1_000_000_000_000
        ? `${(mag / 1_000_000_000_000).toFixed(2)}T`
        : mag >= 100_000_000_000
            ? `${Math.round(mag / 1_000_000_000)}B`
            : mag >= 1_000_000_000
                ? `${(mag / 1_000_000_000).toFixed(2)}B`
                : mag >= 1_000_000
                    ? `${(mag / 1_000_000).toFixed(0)}M`
                    : `${(mag / 1_000).toFixed(0)}k`
    return v < 0 ? `-${body}` : body
}
const round1 = (v) => Math.round(v * 10) / 10
const pct_change = (now, before) => (before > 0 ? Math.round(((now - before) / before) * 100) : null)
const by = (key) => (a, b) => b[key] - a[key]
/** Volume-weighted % over Jita: (fill ISK / units / jita − 1) × 100. Null when Jita is missing. */
const markup_over_jita = (isk, units, jita) => {
    if (!jita || jita <= 0 || !units || units <= 0) return null
    return round1((isk / units / jita - 1) * 100)
}

await mkdir(KILL_CACHE, { recursive: true })
await mkdir(MARKET_CACHE, { recursive: true })
await mkdir(OUT_DIR, { recursive: true })

// ---------------------------------------------------------------- SDE lookups (newest bundled sqlite first, same candidates as sde_db.ts)
const ESI_BASE = 'https://esi.evetech.net/latest'
const ESI_TYPES_CACHE = path.join(MARKET_CACHE, 'esi-types.json')
const empty_type_meta = () => ({
    name: '', group_id: 0, group_name: '', category: '', volume: 0, packaged_volume: null,
})
function resolve_sde_path() {
    const candidates = [
        path.join(ROOT, 'src', 'data', 'sde-3409592.sqlite'),
        path.join(ROOT, 'src', 'data', 'sde-3316380.sqlite'),
    ]
    for (const candidate of candidates) {
        try {
            if (existsSync(candidate) && statSync(candidate).size > 0) return candidate
        } catch { /* try next */ }
    }
    return candidates[candidates.length - 1]
}
const sde_path = resolve_sde_path()
console.error(`sde: ${path.relative(ROOT, sde_path)}`)
const sde = new Database(sde_path, { readonly: true })
const type_row = sde.prepare(`
    SELECT t.typeName AS name, t.groupID AS group_id, g.groupName AS group_name, c.categoryName AS category,
           t.volume AS volume, v.volume AS packaged_volume
    FROM invTypes t
    JOIN invGroups g ON g.groupID = t.groupID
    JOIN invCategories c ON c.categoryID = g.categoryID
    LEFT JOIN invVolumes v ON v.typeID = t.typeID
    WHERE t.typeID = ?`)
const type_cache = new Map()
const type_meta = (tid) => {
    if (!type_cache.has(tid)) {
        type_cache.set(tid, type_row.get(tid) ?? empty_type_meta())
    }
    return type_cache.get(tid)
}
function apply_type_meta(tid, patch) {
    if (!tid) return
    const cur = { ...type_meta(tid) }
    if (patch.name && !cur.name) cur.name = patch.name
    if (patch.group_id && !cur.group_id) cur.group_id = patch.group_id
    if (patch.group_name && !cur.group_name) cur.group_name = patch.group_name
    if (patch.category && !cur.category) cur.category = patch.category
    if (patch.volume && !cur.volume) cur.volume = patch.volume
    if (patch.packaged_volume != null && cur.packaged_volume == null) cur.packaged_volume = patch.packaged_volume
    type_cache.set(tid, cur)
}
/** SDE, then inferred-sales payload, then ESI; last resort is Type {id}. */
const type_label = (t) => type_meta(t.type_id).name || t.name || `Type ${t.type_id}`
const packaged_m3 = (tid) => {
    const meta = type_meta(tid)
    return Number(meta.packaged_volume ?? meta.volume ?? 0)
}
const is_capital = (tid) => CAPITAL_GROUPS.has(type_meta(tid).group_id)
const sys_row = sde.prepare(`
    SELECT s.solarSystemID AS id, s.solarSystemName AS name, r.regionName AS region
    FROM mapSolarSystems s JOIN mapRegions r ON r.regionID = s.regionID
    WHERE s.solarSystemID = ?`)
const sys_meta = (sid) => sys_row.get(sid) ?? { id: sid, name: String(sid), region: '' }

let esi_types_disk = {}
const esi_group_cache = new Map()
const esi_category_cache = new Map()
async function load_esi_types_disk() {
    if (!existsSync(ESI_TYPES_CACHE)) return
    try {
        esi_types_disk = JSON.parse(await readFile(ESI_TYPES_CACHE, 'utf8')) || {}
    } catch {
        esi_types_disk = {}
    }
}
function persist_esi_type(tid) {
    const meta = type_meta(tid)
    if (!meta.name && !meta.category) return
    esi_types_disk[tid] = {
        name: meta.name,
        group_id: meta.group_id,
        group_name: meta.group_name,
        category: meta.category,
        volume: meta.volume,
        packaged_volume: meta.packaged_volume,
    }
}
function apply_sales_payload(rows) {
    for (const t of rows) {
        apply_type_meta(t.type_id, { name: t.name, group_name: t.group, category: t.category })
    }
}
async function esi_group_meta(group_id) {
    if (!group_id) return { group_name: '', category: '' }
    if (esi_group_cache.has(group_id)) return esi_group_cache.get(group_id)
    const group = await fetch_json(`${ESI_BASE}/universe/groups/${group_id}/`)
    let category = ''
    if (group.category_id) {
        if (!esi_category_cache.has(group.category_id)) {
            const cat = await fetch_json(`${ESI_BASE}/universe/categories/${group.category_id}/`)
            esi_category_cache.set(group.category_id, cat.name ?? '')
        }
        category = esi_category_cache.get(group.category_id)
    }
    const meta = { group_name: group.name ?? '', category }
    esi_group_cache.set(group_id, meta)
    return meta
}
/** Fill names/groups/categories for type IDs the bundled SDE does not know yet. */
async function esi_hydrate_types(ids) {
    const unique = [...new Set(ids.filter(Boolean))]
    const incomplete = unique.filter((tid) => {
        const meta = type_meta(tid)
        return !meta.name || !meta.category
    })
    if (!incomplete.length) return 0

    for (const tid of incomplete) {
        const cached = esi_types_disk[tid] ?? esi_types_disk[String(tid)]
        if (cached) apply_type_meta(tid, cached)
    }
    const still = incomplete.filter((tid) => {
        const meta = type_meta(tid)
        return !meta.name || !meta.category
    })
    if (!still.length) return 0

    const nameless = still.filter((tid) => !type_meta(tid).name)
    if (nameless.length) {
        try {
            for (let i = 0; i < nameless.length; i += 1000) {
                const chunk = nameless.slice(i, i + 1000)
                const rows = await fetch_json(`${ESI_BASE}/universe/names/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(chunk),
                })
                for (const row of rows) apply_type_meta(row.id, { name: row.name })
            }
        } catch (error) {
            console.error(`esi names: ${error.message}`)
        }
    }

    const need_type = still.filter((tid) => !type_meta(tid).name || !type_meta(tid).category)
    let fetched = 0
    for (const tid of need_type) {
        try {
            const type = await fetch_json(`${ESI_BASE}/universe/types/${tid}/`)
            const group = await esi_group_meta(type.group_id)
            apply_type_meta(tid, {
                name: type.name,
                group_id: type.group_id,
                group_name: group.group_name,
                category: group.category,
                volume: type.volume,
                packaged_volume: type.packaged_volume ?? null,
            })
            fetched += 1
        } catch (error) {
            console.error(`esi type ${tid}: ${error.message}`)
        }
        persist_esi_type(tid)
    }
    for (const tid of still) persist_esi_type(tid)
    await writeFile(ESI_TYPES_CACHE, JSON.stringify(esi_types_disk))
    console.error(`esi: hydrated ${still.length} types missing from SDE (${fetched} via /universe/types)`)
    return still.length
}

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
const sales_source = sales.source ?? API
const prev_by_type = new Map(sales_prev.by_type.map((t) => [t.type_id, t]))
console.error(`sales: ${sales.totals.fills} fills · ${fmt_isk(sales.totals.isk)} · ${sales.totals.types} types`)

await load_esi_types_disk()
apply_sales_payload(sales.by_type)
apply_sales_payload(sales_prev.by_type)
await esi_hydrate_types([
    ...sales.by_type.map((t) => t.type_id),
    ...sales_prev.by_type.map((t) => t.type_id),
])

const jita_payload = await read_cache_json(`jita-${YEAR}-${pad2(MONTH)}.json`)
const jita_prices = new Map(Object.entries(jita_payload?.prices ?? {}).map(([id, price]) => [Number(id), Number(price)]))
const jita_prev_payload = await read_cache_json(`jita-${prev.year}-${pad2(prev.month)}.json`)
const jita_prev_own = new Map(Object.entries(jita_prev_payload?.prices ?? {}).map(([id, price]) => [Number(id), Number(price)]))
const jita_prev_prices = jita_prev_own.size > 0 ? jita_prev_own : jita_prices
console.error(`jita: ${jita_prices.size} Forge averages${jita_payload?.as_of ? ` as of ${jita_payload.as_of}` : ' (cache missing)'}`)
console.error(`jita prev: ${jita_prev_own.size} Forge averages${jita_prev_payload?.as_of ? ` as of ${jita_prev_payload.as_of}` : jita_prev_own.size ? '' : ' (missing; using this month\'s Jita for MoM profit)'}`)

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

// Category buckets (SDE / ESI category+group → report class).
const bucket_for_type = (t) => {
    const meta = type_meta(t.type_id)
    const category = meta.category || t.category
    const group = meta.group_name || t.group
    if (PLEX_ADJACENT_GROUPS.has(group) || PLEX_ADJACENT_TYPE_IDS.has(t.type_id)) return 'PLEX adjacent'
    if (category === 'Ship') return 'Ships'
    if (category === 'Module' && /rig/i.test(group)) return 'Rigs'
    if (category === 'Module' || category === 'Subsystem') return 'Modules'
    if (category === 'Charge') return 'Charges'
    if (category === 'Drone' || category === 'Fighter') return 'Drones'
    if (category === 'Implant') return 'Implants'
    if (MATERIAL_CATEGORIES.has(category) || MATERIAL_GROUPS.has(group)) return 'Materials & commodities'
    return 'Other'
}
const bucket_totals = (rows) => {
    const out = new Map()
    for (const t of rows) {
        const b = bucket_for_type(t)
        const cur = out.get(b) ?? { name: b, isk: 0, units: 0, fills: 0, priced_isk: 0, jita_isk: 0 }
        cur.isk += t.isk
        cur.units += t.units
        cur.fills += t.fills
        const jita = jita_prices.get(t.type_id)
        if (jita && jita > 0 && t.units > 0) {
            cur.priced_isk += t.isk
            cur.jita_isk += t.units * jita
        }
        out.set(b, cur)
    }
    return out
}
const buckets_now = bucket_totals(sales.by_type)
const buckets_prev = bucket_totals(sales_prev.by_type)
const CATEGORIES = [...buckets_now.values()]
    .sort(by('isk'))
    .map((b) => {
        const prev_bucket = buckets_prev.get(b.name)
        const isk_vs = b.isk - (prev_bucket?.isk ?? 0)
        const { priced_isk, jita_isk, ...rest } = b
        return {
            ...rest,
            isk_label: fmt_isk(b.isk),
            share: round1((b.isk / Math.max(sales.totals.isk, 1)) * 100),
            isk_vs,
            isk_vs_label: fmt_isk(Math.abs(isk_vs)),
            isk_vs_pct: pct_change(b.isk, prev_bucket?.isk ?? 0),
            units_vs: b.units - (prev_bucket?.units ?? 0),
            fills_vs: b.fills - (prev_bucket?.fills ?? 0),
            markup_pct: jita_isk > 0 ? round1((priced_isk / jita_isk - 1) * 100) : null,
        }
    })

// Top types by inferred ISK (editorial exclusions via --exclude).
const to_type_row = (t) => {
    const p = prev_by_type.get(t.type_id)
    return {
        typeId: t.type_id,
        name: type_label(t),
        category: bucket_for_type(t),
        isk: t.isk,
        isk_label: fmt_isk(t.isk),
        units: t.units,
        fills: t.fills,
        share: round1((t.isk / Math.max(sales.totals.isk, 1)) * 100),
        isk_vs_pct: p ? pct_change(t.isk, p.isk) : null,
        is_new: !p,
        markup_pct: markup_over_jita(t.isk, t.units, jita_prices.get(t.type_id)),
    }
}
const ranked_types = sales.by_type
    .filter((t) => !EXCLUDE_TYPE_IDS.has(t.type_id))
    .sort(by('isk'))
    .map(to_type_row)
const TOP_TYPES = ranked_types.slice(0, TOP)
const TOP_TYPES_BY_CLASS = Object.fromEntries(
    CATEGORIES.map((bucket) => [
        bucket.name,
        ranked_types.filter((row) => row.category === bucket.name).slice(0, TOP),
    ]).filter(([, rows]) => rows.length > 0),
)

// ---------------------------------------------------------------- Destruction feed
const fw = await fetch_json('https://esi.evetech.net/latest/fw/systems/')
const wz = fw.filter((s) => [500002, 500003].includes(s.owner_faction_id))
const holder = new Map(wz.map((s) => [s.solar_system_id, MILITIAS[s.occupier_faction_id] ?? MILITIAS[s.owner_faction_id]]))
const system_ids = wz.map((s) => s.solar_system_id)
if (!system_ids.includes(AMAMAKE_SYSTEM_ID)) system_ids.push(AMAMAKE_SYSTEM_ID)
console.error(`kills: ${system_ids.length} FW systems from ESI · cache ${KILL_CACHE}`)

const system_stats = new Map() // sid -> {ships, isk, capital_isk, capital_ships, ships_prev, isk_prev}
let amamake_kills = []
const unique_chars = new Set()
const lost_now = new Map()
const lost_prev = new Map()
const add_lost = (map, rows) => {
    for (const k of rows) {
        const tid = k.victim?.ship_type_id
        if (tid) map.set(tid, (map.get(tid) ?? 0) + 1)
    }
}
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
    add_lost(lost_now, now)
    add_lost(lost_prev, before)
    if (sid === AMAMAKE_SYSTEM_ID) {
        amamake_kills = now
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

// Died vs sold: hulls lost in the Amarr–Minmatar warzone vs inferred sells at Amamake.
const sold_by_type = new Map(sales.by_type.map((t) => [t.type_id, t.units]))
await esi_hydrate_types([...lost_now.keys(), ...lost_prev.keys()])
const hull_ids = new Set([...lost_now.keys(), ...sales.by_type.filter((t) => type_meta(t.type_id).category === 'Ship').map((t) => t.type_id)])
const HULLS = [...hull_ids]
    .filter((tid) => type_meta(tid).category === 'Ship' && !EXCLUDE_TYPE_IDS.has(tid))
    .map((tid) => {
        const sold = sold_by_type.get(tid) ?? 0
        const lost = lost_now.get(tid) ?? 0
        return {
            typeId: tid,
            name: type_meta(tid).name || `Type ${tid}`,
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

/**
 * Items worth seeding: extra ISK among types that can take another hauler
 * without instantly cooking the Amamake book.
 *
 * August 2026, types already ≥5% vs Jita (freight ignored for the
 * distribution): fills p25/p50 = 10 / 29, units p25 = 21. Floor is 25
 * inferred fills and 25 units — just under median fills, just over the
 * units quartile — so 9-fill / 11-unit outliers drop. Rank by extra ISK
 * (spread × units), not fattest % on a 1-fill hull or BPC. SDE blueprints
 * are excluded below.
 */
const MARGIN_TOP = 10
const MARGIN_MIN_FILLS = 25
const MARGIN_MIN_UNITS = 25
const MARGIN_MIN_PCT = 5

function contract_hulls(payload) {
    const by_hull = new Map()
    let unmatched = 0
    let isk = 0
    let count = 0
    for (const row of payload?.contracts ?? []) {
        count += 1
        isk += row.price ?? 0
        const sid = row.ship_id
        if (!sid) {
            unmatched += 1
            continue
        }
        const cur = by_hull.get(sid) ?? { typeId: sid, name: type_meta(sid).name, group: type_meta(sid).group_name, isk: 0, count: 0 }
        cur.isk += row.price ?? 0
        cur.count += 1
        by_hull.set(sid, cur)
    }
    return { by_hull, unmatched, isk, count }
}

const contracts_now = await read_cache_json(`contracts-${LOCATION_ID}-${YEAR}-${pad2(MONTH)}.json`)
const contracts_prev = await read_cache_json(`contracts-${LOCATION_ID}-${prev.year}-${pad2(prev.month)}.json`)
await esi_hydrate_types([
    ...(contracts_now?.contracts ?? []).map((row) => row.ship_id),
    ...(contracts_prev?.contracts ?? []).map((row) => row.ship_id),
])
const contract_now = contract_hulls(contracts_now)
const contract_prev = contract_hulls(contracts_prev)
const prev_contract_hull = contract_prev.by_hull
const CONTRACT_HULLS = [...contract_now.by_hull.values()]
    .sort(by('isk'))
    .slice(0, TOP_HULLS)
    .map((row) => {
        const before = prev_contract_hull.get(row.typeId)
        return {
            typeId: row.typeId,
            name: row.name,
            group: row.group,
            isk: row.isk,
            isk_label: fmt_isk(row.isk),
            count: row.count,
            isk_vs: row.isk - (before?.isk ?? 0),
            count_vs: row.count - (before?.count ?? 0),
            share: round1((row.isk / Math.max(contract_now.isk, 1)) * 100),
        }
    })
const CONTRACTS = contracts_now
    ? {
        count: contract_now.count,
        count_vs: contract_now.count - contract_prev.count,
        isk: contract_now.isk,
        isk_label: fmt_isk(contract_now.isk),
        isk_vs: contract_now.isk - contract_prev.isk,
        unmatched: contract_now.unmatched,
        matched: contract_now.count - contract_now.unmatched,
    }
    : null

const MARGINS = (jita_payload ? sales.by_type : [])
    .filter((t) => !EXCLUDE_TYPE_IDS.has(t.type_id) && t.fills >= MARGIN_MIN_FILLS && t.units >= MARGIN_MIN_UNITS)
    .map((t) => {
        const jita = jita_prices.get(t.type_id)
        if (!jita || jita <= 0) return null
        const sde_category = type_meta(t.type_id).category || t.category
        if (sde_category === 'Blueprint') return null
        const category = bucket_for_type(t)
        const amamake_avg = t.isk / t.units
        const freight = packaged_m3(t.type_id) * FREIGHT_ISK_PER_M3
        const landed = jita + freight
        if (landed <= 0) return null
        const margin = amamake_avg - landed
        const margin_pct = (margin / landed) * 100
        if (margin_pct < MARGIN_MIN_PCT) return null
        const extra_isk = margin * t.units
        if (extra_isk <= 0) return null
        return {
            typeId: t.type_id,
            name: type_label(t),
            category,
            units: t.units,
            fills: t.fills,
            isk: t.isk,
            isk_label: fmt_isk(t.isk),
            amamake_avg,
            jita,
            freight,
            landed,
            margin,
            margin_pct: round1(margin_pct),
            extra_isk,
            extra_isk_label: fmt_isk(extra_isk),
        }
    })
    .filter(Boolean)
    .sort(by('extra_isk'))
    .slice(0, MARGIN_TOP)
const JITA_AS_OF = jita_payload?.as_of ?? null

function inferred_profit(rows, prices) {
    let profit = 0
    let types_priced = 0
    let types_unpriced = 0
    for (const t of rows) {
        if (!t.units || t.units <= 0) continue
        const jita = prices.get(t.type_id)
        if (!jita || jita <= 0) {
            types_unpriced += 1
            continue
        }
        const freight = packaged_m3(t.type_id) * FREIGHT_ISK_PER_M3
        profit += t.isk - (jita + freight) * t.units
        types_priced += 1
    }
    return { profit, types_priced, types_unpriced }
}

const profit_now = inferred_profit(sales.by_type, jita_prices)
const profit_prev = inferred_profit(sales_prev.by_type, jita_prev_prices)

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
    profit: profit_now.profit - profit_prev.profit,
    profit_pct: pct_change(profit_now.profit, profit_prev.profit),
}

const ts = (name, type, value) => `export const ${name}: ${type} = ${JSON.stringify(value, null, 4)}\n`
const out = [
    `// Generated by scripts/amamake_market_extract.mjs — do not hand-edit; re-run instead.`,
    `// node scripts/amamake_market_extract.mjs --year ${YEAR} --month ${MONTH} --slug ${SLUG}`,
    `// Sales: ${sales_source} inferred-sales/monthly · Kills: zKillboard per-system cache · Extracted ${today.toISOString()}`,
    ``,
    `import type {`,
    `    MarketCapitalSplitRow,`,
    `    MarketCatchmentRow,`,
    `    MarketCategoryRow,`,
    `    MarketContractHullRow,`,
    `    MarketContractTotals,`,
    `    MarketDayRow,`,
    `    MarketHubHealth,`,
    `    MarketHullRow,`,
    `    MarketMarginRow,`,
    `    MarketPipe,`,
    `    MarketRegionRow,`,
    `    MarketSalesTotals,`,
    `    MarketSalesTotalsVs,`,
    `    MarketSystemSummary,`,
    `    MarketTopTypeRow,`,
    `    MarketTopTypesByClass,`,
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
        profit: profit_now.profit,
        profit_label: fmt_isk(profit_now.profit),
        profit_types: profit_now.types_priced,
        profit_unpriced_types: profit_now.types_unpriced,
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
        profit: profit_prev.profit,
        profit_label: fmt_isk(profit_prev.profit),
        profit_types: profit_prev.types_priced,
        profit_unpriced_types: profit_prev.types_unpriced,
        days_with_sales: sales_prev.days.length,
        loudest_day: null,
        quietest_day: null,
    }),
    ts('SALES_TOTALS_VS', 'MarketSalesTotalsVs', sales_vs),
    ts('DAYS', 'readonly MarketDayRow[]', DAYS),
    ts('WEEKS', 'readonly MarketWeekRow[]', WEEKS.map((w) => ({ ...w, isk_label: fmt_isk(w.isk) }))),
    ts('CATEGORIES', 'readonly MarketCategoryRow[]', CATEGORIES),
    ts('TOP_TYPES', 'readonly MarketTopTypeRow[]', TOP_TYPES),
    ts('TOP_TYPES_BY_CLASS', 'MarketTopTypesByClass', TOP_TYPES_BY_CLASS),
    ts('HULLS', 'readonly MarketHullRow[]', HULLS_TOP),
    `export const HULLS_SOLD_TOTAL = ${hulls_sold_total}`,
    `export const HULLS_LOST_TOTAL = ${hulls_lost_total}`,
    ts('AMAMAKE', 'MarketSystemSummary', AMAMAKE),
    ts('WARZONE', 'MarketWarzoneSummary', WARZONE),
    ts('CATCHMENT', 'readonly MarketCatchmentRow[]', CATCHMENT),
    ts('REGIONS', 'readonly MarketRegionRow[]', REGIONS),
    ts('PIPE', 'MarketPipe', PIPE),
    ts('CAPITAL_SPLIT', 'readonly MarketCapitalSplitRow[]', CAPITAL_SPLIT),
    ts('CONTRACTS', 'MarketContractTotals | null', CONTRACTS),
    ts('CONTRACT_HULLS', 'readonly MarketContractHullRow[]', CONTRACT_HULLS),
    ts('MARGINS', 'readonly MarketMarginRow[]', MARGINS),
    `export const JITA_AS_OF = ${JSON.stringify(JITA_AS_OF)}`,
    `export const FREIGHT_ISK_PER_M3 = ${FREIGHT_ISK_PER_M3}`,
    `export const FREIGHT_ROUTE_LABEL = ${JSON.stringify(FREIGHT_ROUTE_LABEL)}`,
    ts('HUB_HEALTH', 'MarketHubHealth | null', HUB_HEALTH),
].join('\n')

const published_names = [
    ...TOP_TYPES,
    ...Object.values(TOP_TYPES_BY_CLASS).flat(),
    ...HULLS_TOP,
    ...CONTRACT_HULLS,
    ...MARGINS,
]
const fallback_names = published_names.filter((row) => /^Type \d+$/.test(row.name))
if (fallback_names.length) {
    console.error(`warning: ${fallback_names.length} published rows still use Type {id}: ${fallback_names.map((row) => row.typeId).join(', ')}`)
}

await writeFile(OUT_FILE, out)
console.error(`wrote ${path.relative(ROOT, OUT_FILE)}`)
console.error(`  sales ${fmt_isk(sales.totals.isk)} (${sales_vs.isk_pct ?? '—'}% vs prior) · ${sales.totals.fills} fills · ${sales.totals.units} units`)
console.error(`  profit ${fmt_isk(profit_now.profit)} (${sales_vs.profit_pct ?? '—'}% vs prior) · ${profit_now.types_priced} priced / ${profit_now.types_unpriced} no Jita · freight ${FREIGHT_ISK_PER_M3} ISK/m³ ${FREIGHT_ROUTE_LABEL}`)
console.error(`  Amamake ${AMAMAKE.ships} ships (${AMAMAKE.share_of_warzone}% of ${WARZONE.ships}) · ${AMAMAKE.isk_label} · ${AMAMAKE.unique_characters} characters`)
console.error(`  top type ${TOP_TYPES[0]?.name} ${TOP_TYPES[0]?.isk_label} · top hull ${HULLS_TOP[0]?.name} ${HULLS_TOP[0]?.sold} sold / ${HULLS_TOP[0]?.lost} lost`)
console.error(`  contracts ${CONTRACTS ? `${CONTRACTS.count} / ${CONTRACTS.isk_label}` : 'none'} · margins ${MARGINS.length} types · days ${sales.days.length}/${days_in_month}`)
