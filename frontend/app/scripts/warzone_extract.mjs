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
 *
 * Output: src/data/warzone/<slug>-boards.ts   (do not hand-edit; re-run instead)
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
const TOP = Number(args.top ?? 5)
const TOP_GROUPS = Number(args.groups ?? 10)
const TOP_TRAFFIC = Number(args.traffic ?? 12)
const MIN_GROUP_KILLS = 25
const FW_SHARE_THRESHOLD = 0.5
if (!YEAR || !MONTH || !SLUG) {
    console.error('usage: node scripts/warzone_extract.mjs --year 2026 --month 7 --slug yc128-07')
    process.exit(1)
}

const USER_AGENT = process.env.ZKILL_USER_AGENT ?? 'my.minmatar.org warzone-report script'
const MILITIAS = { 500002: 'minmatar', 500003: 'amarr' }
const FACTION_NAMES = { 500002: 'Minmatar Republic', 500003: 'Amarr Empire', 500011: 'Angel Cartel', 500010: 'Guristas Pirates', 500001: 'Caldari State', 500004: 'Gallente Federation' }
const CAPSULES = new Set([670, 33328])
const ROOT = path.resolve(import.meta.dirname, '..')
const CACHE = path.join(ROOT, '.cache', 'warzone', 'systems')
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
const bucket_for = (n) => (n <= 1 ? 'solo' : n <= 24 ? 'small_gang' : 'fleet')

await mkdir(CACHE, { recursive: true })

// SDE: system -> {name, region, constellation}
const sde = new Database(path.join(ROOT, 'src', 'data', 'sde-3316380.sqlite'), { readonly: true })
const sde_row = sde.prepare(`
    SELECT s.solarSystemName AS name, r.regionName AS region, c.constellationName AS constellation
    FROM mapSolarSystems s
    JOIN mapRegions r ON r.regionID = s.regionID
    JOIN mapConstellations c ON c.constellationID = s.constellationID
    WHERE s.solarSystemID = ?`)
const sys_meta = (sid) => sde_row.get(sid) ?? { name: String(sid), region: '', constellation: '' }

// FW systems + current holder
const fw = await fetch_json('https://esi.evetech.net/latest/fw/systems/')
const wz = fw.filter((s) => [500002, 500003].includes(s.owner_faction_id))
const holder = new Map(wz.map((s) => [s.solar_system_id, MILITIAS[s.occupier_faction_id] ?? MILITIAS[s.owner_faction_id]]))
const system_ids = wz.map((s) => s.solar_system_id)
console.error(`FW systems: ${system_ids.length}`)

// FW stats (scoreboard)
const stats = await fetch_json('https://esi.evetech.net/latest/fw/stats/')
const stat_of = (fid) => stats.find((s) => s.faction_id === fid)
const scoreboard = {}
for (const [fid, key] of [[500002, 'minmatar'], [500003, 'amarr']]) {
    const s = stat_of(fid)
    scoreboard[key] = {
        systems: s.systems_controlled,
        pilots: s.pilots,
        kills_last_week: s.kills.last_week,
        vp_last_week: s.victory_points.last_week,
    }
}

// Gather kills per system for both months.
const per_system = new Map() // sid -> {ships, isk}
const per_system_prev = new Map()
const counts = { minmatar: { solo: new Map(), small_gang: new Map(), fleet: new Map() }, amarr: { solo: new Map(), small_gang: new Map(), fleet: new Map() } }
const affil = new Map() // character_id -> Map(`${kind}:${id}` -> count)
const bump = (map, key) => map.set(key, (map.get(key) ?? 0) + 1)
const groups = new Map()
const group_stat = (key) => {
    if (!groups.has(key)) {
        const [kind, id] = key.split(':')
        groups.set(key, { kind, id: Number(id), killmails: 0, isk: 0, losses: 0, minmatar: 0, amarr: 0, factions: new Map() })
    }
    return groups.get(key)
}
const is_npc_corp = (id) => id >= 1_000_000 && id < 2_000_000
const group_key = (e) =>
    e?.alliance_id ? `alliance:${e.alliance_id}` : e?.corporation_id && !is_npc_corp(e.corporation_id) ? `corporation:${e.corporation_id}` : null

let total_ships = 0
let total_isk = 0
let done = 0
const militia_kills = { minmatar: 0, amarr: 0 }
const active_pilots = { minmatar: new Set(), amarr: new Set() }
for (const sid of system_ids) {
    const cur = clean(await system_month_kills(sid, YEAR, MONTH), YEAR, MONTH)
    const pv = clean(await system_month_kills(sid, prev.year, prev.month), prev.year, prev.month)
    per_system.set(sid, { ships: cur.length, isk: cur.reduce((a, k) => a + (k.zkb?.totalValue ?? 0), 0) })
    per_system_prev.set(sid, { ships: pv.length })
    for (const k of cur) {
        total_ships += 1
        total_isk += k.zkb?.totalValue ?? 0
        const players = k.attackers.filter((a) => a.character_id)
        const bucket = bucket_for(players.length)
        const militias_on = new Set(players.map((a) => MILITIAS[a.faction_id]).filter(Boolean))
        if (militias_on.has('minmatar')) militia_kills.minmatar += 1
        if (militias_on.has('amarr')) militia_kills.amarr += 1
        for (const a of players) {
            const m = MILITIAS[a.faction_id]
            if (m) {
                counts[m][bucket].set(a.character_id, (counts[m][bucket].get(a.character_id) ?? 0) + 1)
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
        if (!Array.isArray(rows) || rows.length === 0) { exhausted = true; break }
        total += rows.filter((k) => !CAPSULES.has(k.victim?.ship_type_id) && !k.zkb?.npc).length
        if (total > limit) break
        if (rows.length < 200) { exhausted = true; break }
        page += 1
    }
    const share = exhausted && total > 0 ? g.killmails / total : 0
    if (share > FW_SHARE_THRESHOLD) {
        const dominant = [...g.factions.entries()].sort((a, b) => b[1] - a[1])[0]
        const dominant_id = dominant ? dominant[0] : null
        const faction = dominant_id ? (FACTION_NAMES[dominant_id] ?? 'Neutral') : 'Neutral'
        const militia = dominant_id === 500002 ? 'minmatar' : dominant_id === 500003 ? 'amarr' : null
        qualified.push({ ...g, share, faction, faction_id: dominant_id, militia_label: militia })
        name_ids.add(g.id)
    }
    console.error(`  ${g.kind} ${g.id}: ${g.killmails}/${exhausted ? total : '>' + Math.floor(limit)} -> ${share > FW_SHARE_THRESHOLD ? 'keep' : 'drop'}`)
}

// Traffic rows: top systems by ships this month.
const traffic = system_ids
    .map((sid) => {
        const cur = per_system.get(sid) ?? { ships: 0, isk: 0 }
        const pv = per_system_prev.get(sid) ?? { ships: 0 }
        const meta = sys_meta(sid)
        return { sid, ...meta, ships: cur.ships, isk: Math.round(cur.isk), vs: cur.ships - pv.ships, holds: holder.get(sid) }
    })
    .filter((r) => r.ships > 0)
    .sort((a, b) => b.ships - a.ships)
    .slice(0, TOP_TRAFFIC)

// Front aggregates over all systems (Minmatar front = Heimatar+Metropolis, Amarr front = Devoid+Bleak Lands).
const FRONT_REGIONS = { minmatar: ['Heimatar', 'Metropolis'], amarr: ['Devoid', 'The Bleak Lands'] }
const region_front = (region) =>
    FRONT_REGIONS.minmatar.includes(region) ? 'minmatar' : FRONT_REGIONS.amarr.includes(region) ? 'amarr' : null
const fronts = { minmatar: { ships: 0, isk: 0, hottest: null }, amarr: { ships: 0, isk: 0, hottest: null } }
const system_stats = []
for (const sid of system_ids) {
    const cur = per_system.get(sid) ?? { ships: 0, isk: 0 }
    const pv = per_system_prev.get(sid) ?? { ships: 0 }
    const meta = sys_meta(sid)
    const front = region_front(meta.region)
    system_stats.push({ sid, name: meta.name, region: meta.region, front, ships: cur.ships, isk: Math.round(cur.isk), vs: cur.ships - pv.ships, holds: holder.get(sid) })
    if (front) {
        fronts[front].ships += cur.ships
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
const front_of = (region, constellation) =>
    region === 'Heimatar' ? 'Heimatar' : region === 'Metropolis' ? 'Metropolis' : region === 'The Bleak Lands' ? 'Bleak Lands' : region === 'Devoid' ? 'Devoid' : constellation
const pilots_ts = (rows) => rows.map(([id, km]) => {
    const aff = top_affiliation(id)
    const aff_name = aff ? (names.get(aff.id) ?? String(aff.id)) : ''
    return `    { characterId: ${ti(id)}, name: ${JSON.stringify(names.get(id) ?? String(id))}, killmails: ${km}, affiliation: ${JSON.stringify(aff_name)}, affiliation_id: ${aff ? ti(aff.id) : 0}, affiliation_kind: ${JSON.stringify(aff ? aff.kind : 'corporation')} },`
}).join('\n')
const militia_of = (g) => (g.minmatar === 0 && g.amarr === 0 ? 'null' : g.minmatar >= g.amarr ? "'minmatar'" : "'amarr'")
const groups_ts = (rows) => rows.map((g) => `    { id: ${ti(g.id)}, kind: '${g.kind}', name: ${JSON.stringify(names.get(g.id) ?? String(g.id))}, killmails: ${ti(g.killmails)}, isk_destroyed: ${ti(g.isk)}, ships_lost: ${ti(g.losses)}, militia: ${g.militia_label ? `'${g.militia_label}'` : 'null'}, faction: ${JSON.stringify(g.faction)}, faction_id: ${g.faction_id ?? 'null'}, fw_share: ${g.share.toFixed(2)} },`).join('\n')
const traffic_ts = (rows) => rows.map((r) => `    { system: ${JSON.stringify(r.name)}, system_id: ${ti(r.sid)}, front: ${JSON.stringify(front_of(r.region, r.constellation))}, ships: ${ti(r.ships)}, vs_last_month: ${r.vs}, isk: ${ti(r.isk)}, isk_label: ${JSON.stringify(isk_label(r.isk))}, holds_today: ${JSON.stringify(r.holds)}, href: ${JSON.stringify(`https://zkillboard.com/system/${r.sid}/`)} },`).join('\n')

const today = new Date().toISOString().slice(0, 10)
const BL = { solo: 'SOLO', small_gang: 'SMALL_GANG', fleet: 'FLEET' }
let out = `/**
 * Warzone Report boards for ${SLUG} — generated by scripts/warzone_extract.mjs on ${today}.
 * Source: zKillboard per-system kills for all ${system_ids.length} Amarr-Minmatar FW systems in ${YEAR}-${String(MONTH).padStart(2, '0')}
 * (capsules and NPC-only kills excluded); deltas vs ${prev.year}-${String(prev.month).padStart(2, '0')}; holders and scoreboard from ESI.
 * Do not edit by hand; re-run the script.
 */

import type { WarzoneGroup, WarzonePilot, WarzoneTrafficRow } from './types'

export const BOARDS_GENERATED_ON = '${today}'
export const BOARDS_SAMPLED_KILLS = ${ti(total_ships)}
export const BOARDS_TOTAL_ISK = ${ti(total_isk)}

export const SCOREBOARD_STATS = {
    minmatar: { systems: ${scoreboard.minmatar.systems}, pilots: ${scoreboard.minmatar.pilots}, active_pilots: ${active_pilots.minmatar.size}, kills: ${militia_kills.minmatar}, kills_last_week: ${scoreboard.minmatar.kills_last_week}, victory_points_last_week: ${scoreboard.minmatar.vp_last_week} },
    amarr: { systems: ${scoreboard.amarr.systems}, pilots: ${scoreboard.amarr.pilots}, active_pilots: ${active_pilots.amarr.size}, kills: ${militia_kills.amarr}, kills_last_week: ${scoreboard.amarr.kills_last_week}, victory_points_last_week: ${scoreboard.amarr.vp_last_week} },
} as const
`
for (const m of ['minmatar', 'amarr']) for (const b of ['solo', 'small_gang', 'fleet'])
    out += `\nexport const ${m.toUpperCase()}_${BL[b]}: readonly WarzonePilot[] = [\n${pilots_ts(boards[m][b])}\n]\n`
out += `\nexport const GROUPS: readonly WarzoneGroup[] = [\n${groups_ts(qualified)}\n]\n`
out += `\nexport const TRAFFIC: readonly WarzoneTrafficRow[] = [\n${traffic_ts(traffic)}\n]\n`
const front_ships_label = (v) => (v >= 1000 ? `~${Math.round(v / 1000)}k` : String(v))
out += `\nexport const FRONTS = {
    minmatar: { ships: ${ti(fronts.minmatar.ships)}, ships_label: ${JSON.stringify(front_ships_label(fronts.minmatar.ships))}, hottest_system: ${JSON.stringify(fronts.minmatar.hottest?.name ?? '')} },
    amarr: { ships: ${ti(fronts.amarr.ships)}, ships_label: ${JSON.stringify(front_ships_label(fronts.amarr.ships))}, hottest_system: ${JSON.stringify(fronts.amarr.hottest?.name ?? '')} },
} as const
`
const stats_rows = system_stats
    .filter((r) => r.ships > 0)
    .sort((a, b) => b.ships - a.ships)
    .map((r) => `    { system_id: ${ti(r.sid)}, system: ${JSON.stringify(r.name)}, front: ${JSON.stringify(front_of(r.region, r.region))}, ships: ${ti(r.ships)}, vs_last_month: ${r.vs}, isk: ${ti(r.isk)}, isk_label: ${JSON.stringify(isk_label(r.isk))}, holds_today: ${JSON.stringify(r.holds)} },`)
    .join('\n')
out += `\nexport const SYSTEM_STATS = [\n${stats_rows}\n] as const
`
await writeFile(OUT_FILE, out)
console.error(`\nWrote ${path.relative(ROOT, OUT_FILE)} · ${total_ships} ships · ${qualified.length} groups · ${traffic.length} traffic rows`)
