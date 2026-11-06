#!/usr/bin/env node
/**
 * Authoritative data extractor for a Warzone Report issue.
 *
 * Queries every Amarr–Minmatar faction-warfare system (from ESI /fw/systems/)
 * directly on zKillboard — the region kills API is capped for busy regions and
 * undercounts, so per-system queries are the only complete source. Resolves
 * names, regions and constellations from the local SDE sqlite.
 *
 * Produces, for the target month (with the prior month for deltas):
 *   - pilot boards per militia (solo / small gang / fleet)
 *   - groups of the month (alliances or player corps, >50% of kills in the warzone)
 *   - per-system destruction (ships, ISK, vs prior month), current holder
 *   - warzone totals
 *   - live scoreboard stats from ESI /fw/stats/ and /fw/systems/
 *
 * Usage:
 *   node scripts/warzone_extract.mjs --year 2026 --month 7 --slug yc128-07 [--top 5] [--groups 10] [--traffic 12]
 *   node scripts/warzone_extract.mjs --year 2026 --month 10 --slug gallente-caldari-yc128-10 --zone gallente-caldari --compare 0
 *
 * --zone amarr-minmatar (default) | gallente-caldari // pragma: allowlist secret
 * --compare 0 skips the prior month. The first issue of a zone has nothing to diff.
 *
 * Output: src/data/warzone/<slug>-boards.ts   (do not edit by hand; re-run instead)
 */
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'
import { resolve_sde_path } from '../src/helpers/sde_path.mjs'

const args = Object.fromEntries(
    process.argv.slice(2).reduce((p, t, i, l) => (t.startsWith('--') && p.push([t.slice(2), l[i + 1]]), p), []),
)
const YEAR = Number(args.year)
const MONTH = Number(args.month)
const SLUG = args.slug
const TOP = Number(args.top ?? 5)
const TOP_GROUPS = Number(args.groups ?? 10)
const TOP_TRAFFIC = Number(args.traffic ?? 12)
const MIN_GROUP_KILLS = 25
const FW_SHARE_THRESHOLD = 0.5
const ZONE_ID = args.zone ?? 'amarr-minmatar' // pragma: allowlist secret
const COMPARE = args.compare !== '0' && args.compare !== 'false'
if (!YEAR || !MONTH || !SLUG) {
    console.error('usage: node scripts/warzone_extract.mjs --year 2026 --month 7 --slug yc128-07 [--zone gallente-caldari] [--compare 0]')
    process.exit(1)
}

const ZONES = {
    'amarr-minmatar': { // pragma: allowlist secret
        title: 'Amarr-Minmatar', // pragma: allowlist secret
        sides: [
            { id: 'minmatar', faction_id: 500002, dotlan: 'Minmatar Republic', regions: ['Heimatar', 'Metropolis'], region_label: { Heimatar: 'Heimatar', Metropolis: 'Metropolis' } }, // pragma: allowlist secret
            { id: 'amarr', faction_id: 500003, dotlan: 'Amarr Empire', regions: ['Devoid', 'The Bleak Lands'], region_label: { Devoid: 'Devoid', 'The Bleak Lands': 'Bleak Lands' } },
        ],
    },
    'gallente-caldari': {
        title: 'Gallente-Caldari',
        sides: [
            { id: 'gallente', faction_id: 500004, dotlan: 'Gallente Federation', regions: ['Placid', 'Essence', 'Verge Vendor'], region_label: { Placid: 'Placid', Essence: 'Essence', 'Verge Vendor': 'Verge Vendor' } },
            { id: 'caldari', faction_id: 500001, dotlan: 'Caldari State', regions: ['Black Rise', 'The Citadel', 'Lonetrek'], region_label: { 'Black Rise': 'Black Rise', 'The Citadel': 'Citadel', Lonetrek: 'Lonetrek' } },
        ],
    },
}
const ZONE = ZONES[ZONE_ID]
if (!ZONE) {
    console.error(`unknown --zone ${ZONE_ID}`)
    process.exit(1)
}
const SIDES = ZONE.sides
const SIDE_IDS = SIDES.map((side) => side.id)

const USER_AGENT = process.env.ZKILL_USER_AGENT ?? 'my.minmatar.org warzone-report script'
const MILITIAS = Object.fromEntries(SIDES.map((side) => [side.faction_id, side.id]))
const HOLDER_IDS = { ...MILITIAS, 500011: 'angel', 500010: 'guristas' }
const FACTION_NAMES = { 500002: 'Minmatar Republic', 500003: 'Amarr Empire', 500011: 'Angel Cartel', 500010: 'Guristas Pirates', 500001: 'Caldari State', 500004: 'Gallente Federation' }
const DOTLAN_HOLDER = { 'Angel Cartel': 'angel', 'Guristas Pirates': 'guristas', ...Object.fromEntries(SIDES.map((side) => [side.dotlan, side.id])) }
const CAPSULES = new Set([670, 33328])
const ROOT = path.resolve(import.meta.dirname, '..')
const CACHE = path.join(ROOT, '.cache', 'warzone', 'systems')
const DOTLAN_CACHE = path.join(ROOT, '.cache', 'warzone', 'dotlan')
const OUT_FILE = path.join(ROOT, 'src', 'data', 'warzone', `${SLUG}-boards.ts`)
const prev = MONTH === 1 ? { year: YEAR - 1, month: 12 } : { year: YEAR, month: MONTH - 1 }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function fetch_json(url, init = {}, attempt = 1) {
    const res = await fetch(url, { ...init, headers: { 'User-Agent': USER_AGENT, Accept: 'application/json', ...(init.headers ?? {}) } })
    if (res.status === 429 || res.status >= 500) {
        if (attempt > 6) throw new Error(`${url} failed (${res.status})`)
        await sleep(Math.min(60_000, 2_000 * 2 ** attempt))
        return fetch_json(url, init, attempt + 1)
    }
    if (!res.ok) throw new Error(`${url} -> ${res.status}`)
    return res.json()
}

async function fetch_text(url, attempt = 1) {
    const res = await fetch(url, { headers: { 'User-Agent': USER_AGENT } })
    if (res.status === 429 || res.status >= 500) {
        if (attempt > 6) throw new Error(`${url} failed (${res.status})`)
        await sleep(Math.min(60_000, 2_000 * 2 ** attempt))
        return fetch_text(url, attempt + 1)
    }
    if (!res.ok) throw new Error(`${url} -> ${res.status}`)
    return res.text()
}

async function system_month_kills(sid, year, month) {
    const all = []
    let page = 1
    for (;;) {
        const file = path.join(CACHE, `${sid}-${year}-${String(month).padStart(2, '0')}-${String(page).padStart(3, '0')}.json`)
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
    const prefix = `${year}-${String(month).padStart(2, '0')}`
    return rows.filter((k) => k.killmail_time?.startsWith(prefix) && !k.zkb?.npc && !CAPSULES.has(k.victim?.ship_type_id))
}
const bucket_for = (n) => (n <= 1 ? 'solo' : n <= 10 ? 'small_gang' : n >= 25 ? 'fleet' : null)

await mkdir(CACHE, { recursive: true })

// SDE when the snapshot is on disk; otherwise ESI. Region names are what the
// front lists key on, and they match between the two.
const meta_by_id = new Map()
let sde_row = null
try {
    const sde = new Database(resolve_sde_path({ root: ROOT }).path, { readonly: true, fileMustExist: true }) // pragma: allowlist secret
    sde_row = sde.prepare(`
        SELECT s.solarSystemName AS name, r.regionName AS region, c.constellationName AS constellation
        FROM mapSolarSystems s
        JOIN mapRegions r ON r.regionID = s.regionID
        JOIN mapConstellations c ON c.constellationID = s.constellationID
        WHERE s.solarSystemID = ?`)
} catch (error) {
    console.error(`SDE snapshot unavailable (${error.message.split('\n')[0]}). Resolving system names from ESI.`)
}
const ESI_META_CACHE = path.join(ROOT, '.cache', 'warzone', 'esi-system-meta.json')
const esi_meta_cache = existsSync(ESI_META_CACHE) ? JSON.parse(await readFile(ESI_META_CACHE, 'utf8')) : {}
async function esi_system_meta(sid) {
    const key = String(sid)
    if (esi_meta_cache[key]) return esi_meta_cache[key]
    const system = await fetch_json(`https://esi.evetech.net/latest/universe/systems/${sid}/`)
    const constellation = await fetch_json(`https://esi.evetech.net/latest/universe/constellations/${system.constellation_id}/`)
    const region = await fetch_json(`https://esi.evetech.net/latest/universe/regions/${constellation.region_id}/`)
    const meta = { name: system.name, region: region.name, constellation: constellation.name }
    esi_meta_cache[key] = meta
    await writeFile(ESI_META_CACHE, JSON.stringify(esi_meta_cache))
    return meta
}
async function load_system_meta(ids) {
    for (const sid of ids) {
        if (sde_row) {
            meta_by_id.set(sid, sde_row.get(sid) ?? { name: String(sid), region: '', constellation: '' })
        } else {
            meta_by_id.set(sid, await esi_system_meta(sid))
        }
    }
}
const sys_meta = (sid) => meta_by_id.get(sid) ?? { name: String(sid), region: '', constellation: '' }

// FW systems + current holder
const fw = await fetch_json('https://esi.evetech.net/latest/fw/systems/')
const wz = fw.filter((s) => SIDES.some((side) => side.faction_id === s.owner_faction_id))
const holder = new Map(wz.map((s) => [s.solar_system_id, HOLDER_IDS[s.occupier_faction_id] ?? HOLDER_IDS[s.owner_faction_id]]))
const system_ids = wz.map((s) => s.solar_system_id)
console.error(`FW systems: ${system_ids.length}`)
await load_system_meta(system_ids)

// FW stats (scoreboard)
const stats = await fetch_json('https://esi.evetech.net/latest/fw/stats/')
const stat_of = (fid) => stats.find((s) => s.faction_id === fid)
const scoreboard = {}
for (const side of SIDES) {
    const s = stat_of(side.faction_id)
    scoreboard[side.id] = {
        systems: s.systems_controlled,
        pilots: s.pilots,
        kills_last_week: s.kills.last_week,
        vp_last_week: s.victory_points.last_week,
    }
}

// Month-end systems held, scored from Dotlan occupancy history. /fw/stats is a
// LIVE count that drifts after the month closes (and is identical for every issue
// generated on the same day), so it is wrong for a monthly retrospective. Dotlan's
// per-system history gives the true holder as of month-end. Each occupancy row lists
// the previous faction first and the new faction last; the table itself is newest-first.
await mkdir(DOTLAN_CACHE, { recursive: true })
const month_end = `${YEAR}-${String(MONTH).padStart(2, '0')}-${String(new Date(YEAR, MONTH, 0).getDate()).padStart(2, '0')}`
const FACTION_RE = /(Amarr Empire|Minmatar Republic|Gallente Federation|Caldari State|Angel Cartel|Guristas Pirates)/g // pragma: allowlist secret
const month_prefix = `${YEAR}-${String(MONTH).padStart(2, '0')}`
const dotlan_rows = (html) => {
    const rows = []
    for (const m of html.matchAll(/<tr[^>]*>[\s\S]*?<\/tr>/g)) {
        const dm = m[0].match(/(20\d\d-\d\d-\d\d)/)
        if (!dm) continue
        const facs = m[0].match(FACTION_RE)
        if (!facs || facs.length < 2) continue
        const tm = m[0].match(/(\d{2}:\d{2})/)
        rows.push({ date: dm[1], time: tm?.[1] ?? '00:00', previous: facs[0], next: facs[facs.length - 1] })
    }
    return rows
}
// Dotlan lists occupancy newest-first. The first row on or before the cutoff is who held the system then.
const dotlan_holder_asof = (rows, cutoff) => {
    for (const row of rows) {
        if (row.date > cutoff) continue
        return row.next
    }
    return null
}
const month_end_systems = Object.fromEntries(SIDE_IDS.map((id) => [id, 0]))
const occupancy_flips = []
let month_end_resolved = 0
for (const sid of system_ids) {
    const meta = sys_meta(sid)
    const name = meta.name.replaceAll(' ', '_')
    const file = path.join(DOTLAN_CACHE, `${name}.html`)
    let html
    try {
        html = await readFile(file, 'utf8')
    } catch {
        html = await fetch_text(`https://evemaps.dotlan.net/system/${encodeURIComponent(name)}`)
        await writeFile(file, html)
        // Dotlan has blocked this script before. One page per system, then a long
        // pause. The HTML is cached, so a re-run does not ask again.
        await sleep(5_000)
    }
    const rows = dotlan_rows(html)
    const owner = dotlan_holder_asof(rows, month_end)
    if (owner) month_end_resolved += 1
    const side_id = SIDES.find((side) => side.dotlan === owner)?.id
    if (side_id) month_end_systems[side_id]++
    for (const row of rows) {
        if (!row.date.startsWith(month_prefix)) continue
        const taken_by = DOTLAN_HOLDER[row.next]
        const previous_owner = DOTLAN_HOLDER[row.previous] ?? null
        if (!taken_by) continue
        occupancy_flips.push({ date: row.date, time: row.time, system: meta.name, system_id: sid, taken_by, previous_owner })
    }
}
occupancy_flips.sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time) || a.system.localeCompare(b.system))
console.error(`Month-end (${month_end}) systems held — ${SIDES.map((side) => `${side.dotlan} ${month_end_systems[side.id]}`).join(', ')} (${month_end_resolved}/${system_ids.length} resolved from Dotlan)`)
// Guard against a Dotlan markup/caching change that would leave systems unparsed:
// only trust the scraped month-end holders when (almost) every system resolved,
// otherwise keep the live /fw/stats count rather than write a skewed scoreboard.
if (month_end_resolved >= system_ids.length - 1) {
    for (const side of SIDES) scoreboard[side.id].systems = month_end_systems[side.id]
} else {
    console.error(
        `WARNING: only ${month_end_resolved}/${system_ids.length} systems resolved from Dotlan; ` +
        `keeping live /fw/stats systems-held counts instead of the month-end scrape.`,
    )
}

// Gather kills per system for both months.
const per_system = new Map() // sid -> {ships, isk}
const per_system_prev = new Map()
const empty_buckets = () => ({ solo: new Map(), small_gang: new Map(), fleet: new Map() })
const counts = Object.fromEntries(SIDE_IDS.map((id) => [id, empty_buckets()]))
const affil = new Map() // character_id -> Map(`${kind}:${id}` -> count)
const bump = (map, key) => map.set(key, (map.get(key) ?? 0) + 1)
const groups = new Map()
const group_stat = (key) => {
    if (!groups.has(key)) {
        const [kind, id] = key.split(':')
        groups.set(key, { kind, id: Number(id), killmails: 0, isk: 0, losses: 0, ...Object.fromEntries(SIDE_IDS.map((id) => [id, 0])), factions: new Map() })
    }
    return groups.get(key)
}
const is_npc_corp = (id) => id >= 1_000_000 && id < 2_000_000
const group_key = (e) =>
    e?.alliance_id ? `alliance:${e.alliance_id}` : e?.corporation_id && !is_npc_corp(e.corporation_id) ? `corporation:${e.corporation_id}` : null

let total_ships = 0
let total_isk = 0
let total_ships_prev = 0
let total_isk_prev = 0
let done = 0
const militia_kills = Object.fromEntries(SIDE_IDS.map((id) => [id, 0]))
const militia_kills_prev = Object.fromEntries(SIDE_IDS.map((id) => [id, 0]))
const active_pilots = Object.fromEntries(SIDE_IDS.map((id) => [id, new Set()]))
const active_pilots_prev = Object.fromEntries(SIDE_IDS.map((id) => [id, new Set()]))
const groups_prev = new Map() // key -> prior-month warzone killmails (for trend + "new" badge)
const ships_by_bucket = { solo: new Map(), small_gang: new Map(), fleet: new Map() }
for (const sid of system_ids) {
    const cur = clean(await system_month_kills(sid, YEAR, MONTH), YEAR, MONTH)
    const pv = COMPARE ? clean(await system_month_kills(sid, prev.year, prev.month), prev.year, prev.month) : []
    per_system.set(sid, { ships: cur.length, isk: cur.reduce((a, k) => a + (k.zkb?.totalValue ?? 0), 0) })
    per_system_prev.set(sid, { ships: pv.length, isk: pv.reduce((a, k) => a + (k.zkb?.totalValue ?? 0), 0) })
    // Prior-month aggregates for month-over-month trend indicators.
    for (const k of pv) {
        total_ships_prev += 1
        total_isk_prev += k.zkb?.totalValue ?? 0
        const seen_prev = new Set()
        const militias_on_prev = new Set()
        for (const a of k.attackers) {
            if (!a.character_id) continue
            const m = MILITIAS[a.faction_id]
            if (m) {
                active_pilots_prev[m].add(a.character_id)
                militias_on_prev.add(m)
            }
            const key = group_key(a)
            if (key && !seen_prev.has(key)) {
                seen_prev.add(key)
                groups_prev.set(key, (groups_prev.get(key) ?? 0) + 1)
            }
        }
        for (const id of SIDE_IDS) if (militias_on_prev.has(id)) militia_kills_prev[id] += 1
    }
    for (const k of cur) {
        total_ships += 1
        total_isk += k.zkb?.totalValue ?? 0
        const players = k.attackers.filter((a) => a.character_id)
        const bucket = bucket_for(players.length)
        const militias_on = new Set(players.map((a) => MILITIAS[a.faction_id]).filter(Boolean))
        for (const id of SIDE_IDS) if (militias_on.has(id)) militia_kills[id] += 1
        const attacker_ships = new Set(players.map((a) => a.ship_type_id).filter((id) => id && !CAPSULES.has(id)))
        if (bucket) for (const st of attacker_ships) ships_by_bucket[bucket].set(st, (ships_by_bucket[bucket].get(st) ?? 0) + 1)
        for (const a of players) {
            const m = MILITIAS[a.faction_id]
            if (m) {
                if (bucket) counts[m][bucket].set(a.character_id, (counts[m][bucket].get(a.character_id) ?? 0) + 1)
                active_pilots[m].add(a.character_id)
            }
            if (!affil.has(a.character_id)) affil.set(a.character_id, new Map())
            const akey = a.alliance_id ? `alliance:${a.alliance_id}` : a.corporation_id ? `corporation:${a.corporation_id}` : null
            if (akey) bump(affil.get(a.character_id), akey)
        }
        const seen = new Set()
        for (const a of k.attackers) {
            if (!a.character_id) continue
            const key = group_key(a)
            if (!key || seen.has(key)) continue
            seen.add(key)
            const g = group_stat(key)
            g.killmails += 1
            g.isk += k.zkb?.totalValue ?? 0
            const m = MILITIAS[a.faction_id]
            if (m) g[m] += 1
            if (a.faction_id) g.factions.set(a.faction_id, (g.factions.get(a.faction_id) ?? 0) + 1)
        }
        const vk = group_key(k.victim)
        if (vk) group_stat(vk).losses += 1
    }
    done += 1
    if (done % 10 === 0) console.error(`  ${done}/${system_ids.length} systems`)
}
console.error(`\n${YEAR}-${MONTH}: ${total_ships} ships, ${(total_isk / 1e12).toFixed(2)}T ISK`)

// Pilot boards.
const top = (map) => [...map.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, TOP)
const boards = {}
const ship_boards = {}
const name_ids = new Set()
const top_affiliation = (cid) => {
    const map = affil.get(cid)
    if (!map || map.size === 0) return null
    const [key] = [...map.entries()].sort((a, b) => b[1] - a[1])[0]
    const [kind, id] = key.split(':')
    return { kind, id: Number(id) }
}
for (const m of Object.keys(counts)) {
    boards[m] = {}
    for (const b of Object.keys(counts[m])) {
        boards[m][b] = top(counts[m][b])
        for (const [id] of boards[m][b]) {
            name_ids.add(id)
            const aff = top_affiliation(id)
            if (aff) name_ids.add(aff.id)
        }
    }
}

// Groups: warzone-share check via zKill group endpoint.
for (const b of ['solo', 'small_gang', 'fleet']) {
    ship_boards[b] = top(ships_by_bucket[b])
    for (const [id] of ship_boards[b]) name_ids.add(id)
}

const candidates = [...groups.values()].filter((g) => g.killmails >= MIN_GROUP_KILLS).sort((a, b) => b.killmails - a.killmails)
console.error(`\nChecking warzone share for ${candidates.length} candidate groups`)
const qualified = []
for (const g of candidates) {
    if (qualified.length >= TOP_GROUPS) break
    const limit = g.killmails / FW_SHARE_THRESHOLD
    let total = 0
    let page = 1
    let exhausted = false
    for (;;) {
        const file = path.join(CACHE, `group-${g.kind}-${g.id}-${YEAR}-${String(MONTH).padStart(2, '0')}-${String(page).padStart(3, '0')}.json`)
        let rows
        if (existsSync(file)) rows = JSON.parse(await readFile(file, 'utf8'))
        else {
            rows = await fetch_json(`https://zkillboard.com/api/kills/${g.kind}ID/${g.id}/year/${YEAR}/month/${MONTH}/page/${page}/`)
            await writeFile(file, JSON.stringify(rows))
            await sleep(1_100)
        }
        // An empty page is the end. A short page is not: zKill sometimes returns
        // fewer than 200 kills on a page that still has older kills behind it.
        if (!Array.isArray(rows) || rows.length === 0) { exhausted = true; break }
        total += rows.filter((k) => !CAPSULES.has(k.victim?.ship_type_id) && !k.zkb?.npc).length
        if (total > limit) break
        page += 1
        if (page > 100) break
    }
    // total < warzone kills means the group feed was incomplete. Don't treat that as a keep.
    const share = exhausted && total >= g.killmails ? g.killmails / total : 0
    if (share > FW_SHARE_THRESHOLD) {
        const dominant = [...g.factions.entries()].sort((a, b) => b[1] - a[1])[0]
        const dominant_id = dominant ? dominant[0] : null
        const faction = dominant_id ? (FACTION_NAMES[dominant_id] ?? 'Neutral') : 'Neutral'
        const militia = dominant_id != null && MILITIAS[dominant_id] ? MILITIAS[dominant_id] : null
        qualified.push({ ...g, share, faction, faction_id: dominant_id, militia_label: militia })
        name_ids.add(g.id)
    }
    console.error(`  ${g.kind} ${g.id}: ${g.killmails}/${exhausted ? total : '>' + Math.floor(limit)} -> ${share > FW_SHARE_THRESHOLD ? 'keep' : 'drop'}`)
}

// Pilot counts next to each group, from ESI (public, no auth). A corporation's
// member_count is on its own record; an alliance is the sum over its member
// corporations. A failed lookup leaves null and the report omits the count.
async function esi_member_count(kind, id) {
    try {
        if (kind === 'corporation') {
            const corp = await fetch_json(`https://esi.evetech.net/latest/corporations/${id}/`)
            return corp.member_count ?? null
        }
        const corp_ids = await fetch_json(`https://esi.evetech.net/latest/alliances/${id}/corporations/`)
        let total = 0
        for (const corp_id of corp_ids) {
            const corp = await fetch_json(`https://esi.evetech.net/latest/corporations/${corp_id}/`)
            total += corp.member_count ?? 0
        }
        return total
    } catch (error) {
        console.error(`  member count for ${kind} ${id} failed: ${error.message}`)
        return null
    }
}
for (const g of qualified) g.pilots = await esi_member_count(g.kind, g.id)

// Traffic rows: top systems by ships this month.
const traffic = system_ids
    .map((sid) => {
        const cur = per_system.get(sid) ?? { ships: 0, isk: 0 }
        const pv = per_system_prev.get(sid) ?? { ships: 0 }
        const meta = sys_meta(sid)
        return { sid, ...meta, ships: cur.ships, isk: Math.round(cur.isk), vs: COMPARE ? cur.ships - pv.ships : 0, holds: holder.get(sid) }
    })
    .filter((r) => r.ships > 0)
    .sort((a, b) => b.ships - a.ships)
    .slice(0, TOP_TRAFFIC)

// Front aggregates over all systems (Minmatar front = Heimatar+Metropolis, Amarr front = Devoid+Bleak Lands).
const region_front = (region) => SIDES.find((side) => side.regions.includes(region))?.id ?? null
const fronts = Object.fromEntries(SIDE_IDS.map((id) => [id, { ships: 0, ships_prev: 0, isk: 0, hottest: null }]))
const system_stats = []
for (const sid of system_ids) {
    const cur = per_system.get(sid) ?? { ships: 0, isk: 0 }
    const pv = per_system_prev.get(sid) ?? { ships: 0 }
    const meta = sys_meta(sid)
    const front = region_front(meta.region)
    system_stats.push({ sid, name: meta.name, region: meta.region, front, ships: cur.ships, isk: Math.round(cur.isk), vs: COMPARE ? cur.ships - pv.ships : 0, holds: holder.get(sid) })
    if (front) {
        fronts[front].ships += cur.ships
        fronts[front].ships_prev += pv.ships
        fronts[front].isk += cur.isk
        if (!fronts[front].hottest || cur.ships > fronts[front].hottest.ships) fronts[front].hottest = { name: meta.name, ships: cur.ships }
    }
}

// Names for pilots + groups.
const names = new Map()
const id_list = [...name_ids]
for (let i = 0; i < id_list.length; i += 500) {
    const chunk = id_list.slice(i, i + 500)
    const r = await fetch_json('https://esi.evetech.net/latest/universe/names/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(chunk),
    })
    for (const e of r) names.set(e.id, e.name)
}

// Emit.
const ti = (v) => Math.round(v).toLocaleString('en-US').replaceAll(',', '_')
const isk_label = (v) => (v >= 1e12 ? `${(v / 1e12).toFixed(2)}T` : v >= 100e9 ? `${Math.round(v / 1e9)}B` : v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : `${Math.round(v / 1e6)}M`)
const front_of = (region, constellation) => {
    for (const side of SIDES) {
        if (side.region_label[region]) return side.region_label[region]
    }
    return constellation
}
const pilots_ts = (rows, prev_set) => rows.map(([id, km]) => {
    const aff = top_affiliation(id)
    const aff_name = aff ? (names.get(aff.id) ?? String(aff.id)) : ''
    return `    { characterId: ${ti(id)}, name: ${JSON.stringify(names.get(id) ?? String(id))}, killmails: ${km}, affiliation: ${JSON.stringify(aff_name)}, affiliation_id: ${aff ? ti(aff.id) : 0}, affiliation_kind: ${JSON.stringify(aff ? aff.kind : 'corporation')}, is_new: ${COMPARE ? !prev_set.has(id) : false} },`
}).join('\n')
const militia_of = (g) => {
    const ranked = SIDES.map((side) => [side.id, g[side.id] ?? 0]).sort((a, b) => b[1] - a[1])
    if (ranked[0][1] === 0) return 'null'
    return `'${ranked[0][0]}'`
}
// Previous month's PUBLISHED board order, for true rank movement. Read the prior
// boards file (regenerated alongside this one) and take its GROUPS order. Rank
// movement is measured against that actual board; a group absent from it is "new
// to the board". If there is no prior board at all, no movement is shown.
async function prev_board_ranks() {
    const dir = path.join(ROOT, 'src', 'data', 'warzone')
    const tag = `${ZONE.title} FW systems in ${prev.year}-${String(prev.month).padStart(2, '0')}`
    const here = path.basename(OUT_FILE)
    for (const f of await readdir(dir)) {
        if (!f.endsWith('-boards.ts') || f === here) continue
        const txt = await readFile(path.join(dir, f), 'utf8')
        if (!txt.includes(tag)) continue
        const block = txt.match(/export const GROUPS[\s\S]*?\n\]/)?.[0] ?? ''
        const ids = [...block.matchAll(/\{ id: ([0-9_]+),/g)].map((m) => Number(m[1].replaceAll('_', '')))
        return new Map(ids.map((id, i) => [id, i + 1]))
    }
    return new Map()
}
const prev_board = await prev_board_ranks()
const has_prev_board = prev_board.size > 0
const groups_ts = (rows) => rows.map((g, i) => {
    const key = `${g.kind}:${g.id}`
    const prev_km = groups_prev.get(key) ?? 0
    const pct = COMPARE && prev_km > 0 ? Math.round(((g.killmails - prev_km) / prev_km) * 100) : null
    const prev_rank = prev_board.get(g.id)
    const rank_delta = COMPARE && prev_rank != null ? prev_rank - (i + 1) : null
    const new_to_board = COMPARE && has_prev_board && prev_rank == null
    return `    { id: ${ti(g.id)}, kind: '${g.kind}', name: ${JSON.stringify(names.get(g.id) ?? String(g.id))}, killmails: ${ti(g.killmails)}, killmails_pct: ${pct}, rank_delta: ${rank_delta}, new_to_board: ${new_to_board}, is_new: ${COMPARE ? prev_km === 0 : false}, isk_destroyed: ${ti(g.isk)}, ships_lost: ${ti(g.losses)}, militia: ${g.militia_label ? `'${g.militia_label}'` : 'null'}, faction: ${JSON.stringify(g.faction)}, faction_id: ${g.faction_id ?? 'null'}, fw_share: ${g.share.toFixed(2)}, pilots: ${g.pilots ?? 'null'} },`
}).join('\n')
const traffic_ts = (rows) => rows.map((r) => `    { system: ${JSON.stringify(r.name)}, system_id: ${ti(r.sid)}, front: ${JSON.stringify(front_of(r.region, r.constellation))}, ships: ${ti(r.ships)}, vs_last_month: ${r.vs}, isk: ${ti(r.isk)}, isk_label: ${JSON.stringify(isk_label(r.isk))}, holds_today: ${JSON.stringify(r.holds ?? null)}, href: ${JSON.stringify(`https://zkillboard.com/system/${r.sid}/`)} },`).join('\n')

const today = new Date().toISOString().slice(0, 10)
const BL = { solo: 'SOLO', small_gang: 'SMALL_GANG', fleet: 'FLEET' }
const vs_field = (n) => (COMPARE ? String(n) : 'null')
const front_ships_label = (v) => (v >= 1000 ? `~${Math.round(v / 1000)}k` : String(v))
const scoreboard_lines = SIDES.map((side) => {
    const id = side.id
    return `    ${id}: { systems: ${scoreboard[id].systems}, pilots: ${scoreboard[id].pilots}, active_pilots: ${active_pilots[id].size}, active_pilots_vs: ${vs_field(active_pilots[id].size - active_pilots_prev[id].size)}, kills: ${militia_kills[id]}, kills_vs: ${vs_field(militia_kills[id] - militia_kills_prev[id])}, kills_last_week: ${scoreboard[id].kills_last_week}, victory_points_last_week: ${scoreboard[id].vp_last_week} },`
}).join('\n')
const front_lines = SIDES.map((side) => {
    const id = side.id
    const front = fronts[id]
    return `    ${id}: { ships: ${ti(front.ships)}, ships_vs: ${vs_field(front.ships - front.ships_prev)}, ships_label: ${JSON.stringify(front_ships_label(front.ships))}, hottest_system: ${JSON.stringify(front.hottest?.name ?? '')} },`
}).join('\n')
let out = `/**
 * Warzone Report boards for ${SLUG} — generated by scripts/warzone_extract.mjs on ${today}.
 * Source: zKillboard per-system kills for all ${system_ids.length} ${ZONE.title} FW systems in ${YEAR}-${String(MONTH).padStart(2, '0')}
 * (capsules and NPC-only kills excluded); ${COMPARE ? `deltas vs ${prev.year}-${String(prev.month).padStart(2, '0')}` : 'no prior-month deltas (first issue of this zone)'}; holders and scoreboard from ESI.
 * Do not edit by hand; re-run the script.
 */

import type { WarzoneGroup, WarzonePilot, WarzoneShip, WarzoneTrafficRow } from './types'

export const ZONE = '${ZONE_ID}'
export const BOARDS_GENERATED_ON = '${today}'
export const BOARDS_SAMPLED_KILLS = ${ti(total_ships)}
export const BOARDS_SAMPLED_KILLS_VS = ${vs_field(total_ships - total_ships_prev)}
export const BOARDS_TOTAL_ISK = ${ti(total_isk)}
export const BOARDS_TOTAL_ISK_VS = ${vs_field(ti(total_isk - total_isk_prev))}

export const SCOREBOARD_STATS = {
${scoreboard_lines}
} as const
`
for (const m of SIDE_IDS) for (const b of ['solo', 'small_gang', 'fleet'])
    out += `\nexport const ${m.toUpperCase()}_${BL[b]}: readonly WarzonePilot[] = [\n${pilots_ts(boards[m][b], active_pilots_prev[m])}\n]\n`
const ships_ts = (rows) => rows.map(([id, count]) => `    { typeId: ${ti(id)}, name: ${JSON.stringify(names.get(id) ?? String(id))}, count: ${count} },`).join('\n')
for (const b of ['solo', 'small_gang', 'fleet'])
    out += `\nexport const SHIPS_${BL[b]}: readonly WarzoneShip[] = [\n${ships_ts(ship_boards[b])}\n]\n`
out += `\nexport const GROUPS: readonly WarzoneGroup[] = [\n${groups_ts(qualified)}\n]\n`
out += `\nexport const TRAFFIC: readonly WarzoneTrafficRow[] = [\n${traffic_ts(traffic)}\n]\n`
out += `\nexport const FRONTS = {
${front_lines}
} as const
`
const stats_rows = system_stats
    .filter((r) => r.ships > 0)
    .sort((a, b) => b.ships - a.ships)
    .map((r) => `    { system_id: ${ti(r.sid)}, system: ${JSON.stringify(r.name)}, front: ${JSON.stringify(front_of(r.region, r.region))}, ships: ${ti(r.ships)}, vs_last_month: ${r.vs}, isk: ${ti(r.isk)}, isk_label: ${JSON.stringify(isk_label(r.isk))}, holds_today: ${JSON.stringify(r.holds ?? null)} },`)
    .join('\n')
out += `\nexport const SYSTEM_STATS = [\n${stats_rows}\n] as const
`
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const flip_rows = occupancy_flips.map((row) => {
    const [, m, d] = row.date.split('-')
    const label = `${Number(d)} ${MONTHS[Number(m) - 1]}`
    return `    { date_label: ${JSON.stringify(label)}, system: ${JSON.stringify(row.system)}, system_id: ${ti(row.system_id)}, taken_by: ${JSON.stringify(row.taken_by)}, previous_owner: ${row.previous_owner ? JSON.stringify(row.previous_owner) : 'null'} },`
}).join('\n')
out += `\nexport const OCCUPANCY_FLIPS = [\n${flip_rows}\n] as const\n`
await writeFile(OUT_FILE, out)
console.error(`\nWrote ${path.relative(ROOT, OUT_FILE)} · ${total_ships} ships · ${qualified.length} groups · ${traffic.length} traffic rows`)
