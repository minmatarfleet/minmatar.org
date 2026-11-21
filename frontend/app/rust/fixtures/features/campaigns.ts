// Fixtures for the Campaigns feature blocks (Features/Campaigns/*).
// Typed with the API types, so `npm run check` fails when the API changes and a fixture no longer fits.
import type {
    CampaignDetail,
    CampaignFitting,
    CampaignLeaderboardRow,
    CampaignCorporationLeaderboardRow,
    CampaignListItem,
    CampaignParty,
    CampaignRosterCorporation,
    CampaignSite,
    CampaignStructure,
    CampaignSystemSummary,
    CampaignTotals,
} from '@dtypes/api.minmatar.org'
import type { CampaignStat } from '@components/blocks/CampaignStatBar.astro'
import type { SystemCardInfo } from '@dtypes/layout_components'

const HOUR = 3_600_000
const DAY = 24 * HOUR
const iso = (offset_ms: number) => new Date(Date.now() + offset_ms).toISOString()

// XFadeScroll's Alpine data (`edge_fade`) comes from the site's footer scripts, which Storybook does not load.
// DataGrid scrolls inside XFadeScroll, so every story that renders a grid needs this shim (as DataGrid.stories.ts does).
export const ensure_edge_fade = () => {
    const w = globalThis as any
    if (w.edge_fade) return
    w.edge_fade = () => ({
        init() {
            const el = (this as any).$el as HTMLElement
            const update = () => {
                el.classList.toggle('fade-start', el.scrollLeft > 0)
                el.classList.toggle('fade-end', el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
            }
            update()
            if (typeof ResizeObserver !== 'undefined') new ResizeObserver(update).observe(el)
            el.addEventListener('scroll', update, { passive: true })
        },
    })
}

// ---------------------------------------------------------------------------
// Parties
// ---------------------------------------------------------------------------

const party = (id: number, name: string, ticker: string, kind: CampaignParty['kind'], side: CampaignParty['side']): CampaignParty => ({
    id, name, ticker, kind, side,
    character_id: null,
    corporation_id: kind === 'corporation' ? id : null,
    alliance_id: kind === 'alliance' ? id : null,
    faction_id: kind === 'faction' ? id : null,
})

export const amarr_empire = party(500003, 'Amarr Empire', '', 'faction', 'enemy')
export const minmatar_republic = party(500002, 'Minmatar Republic', '', 'faction', 'ally')
export const snuffed_out = party(99002685, 'Snuffed Out', 'SNUFF', 'alliance', 'enemy')
export const hostile_parties: CampaignParty[] = [
    snuffed_out,
    party(98700001, 'Clan Vanguard of Amarr', 'CVA', 'alliance', 'enemy'),
    party(98700002, 'Holy Amarrian Defense Order', 'HADO', 'corporation', 'enemy'),
    party(98700003, 'Fourth Hostile Bloc Member', 'FHBM', 'corporation', 'enemy'),
]
export const allied_parties: CampaignParty[] = [
    party(99011978, 'Minmatar Fleet Alliance', 'FL33T', 'alliance', 'ally'),
    party(98726134, 'Rattini Tribe', 'A-RAT', 'corporation', 'ally'),
    party(98700004, 'Republic Fleet Auxiliary', 'RFA', 'corporation', 'ally'),
    party(98700005, 'Fourth Friendly Corporation', 'FFC', 'corporation', 'ally'),
]

// ---------------------------------------------------------------------------
// Systems (from rust/fixtures/sde.json)
// ---------------------------------------------------------------------------

const trend = (values: number[]) => values.map((v, i) => ({
    captured_at: iso(-(values.length - i) * 6 * HOUR),
    contested_percent: v,
    victory_points: Math.round(v * 30),
}))

const system = (over: Partial<CampaignSystemSummary> & Pick<CampaignSystemSummary, 'id' | 'name' | 'solar_system_id'>): CampaignSystemSummary => ({
    role: 'Frontline',
    goal: 'Hold the line',
    priority: 'medium',
    is_fw_objective: true,
    contested_percent: 42,
    contested_change_24h: 3,
    victory_points: 1260,
    victory_points_threshold: 3000,
    operational_state: 'vulnerable',
    contested_updated_at: iso(-12 * 60_000),
    advantage_updated_at: iso(-40 * 60_000),
    occupier_faction_id: 500002,
    owner_faction_id: 500002,
    advantage_basis: 'reading',
    advantage_source: 'pilot',
    advantage_our_pct: 58,
    advantage_enemy_pct: 42,
    advantage_net_pct: 16,
    advantage_age_minutes: 40,
    advantage_is_stale: false,
    kills_24h: 31,
    losses_24h: 14,
    kills_change_24h: 6,
    trend: trend([30, 33, 37, 39, 42]),
    status_chip: 'gaining',
    ...over,
})

export const campaign_systems: CampaignSystemSummary[] = [
    system({ id: 1, name: 'Amamake', solar_system_id: 30002537, role: 'Staging', goal: 'Keep the freeport and the complexes ours', priority: 'high', contested_percent: 61, status_chip: 'holding' }),
    system({ id: 2, name: 'Auga', solar_system_id: 30002542, role: 'Frontline', goal: 'Flip Auga before downtime', priority: 'high', contested_percent: 78, contested_change_24h: 11, status_chip: 'gaining' }),
    system({ id: 3, name: 'Huola', solar_system_id: 30003067, goal: 'Deny Amarr advantage', priority: 'medium', contested_percent: 24, contested_change_24h: -5, victory_points: 480, status_chip: 'losing', occupier_faction_id: 500003 }),
    system({ id: 4, name: 'Vard', solar_system_id: 30002538, goal: 'Support', priority: 'low', is_fw_objective: false, contested_percent: null, contested_change_24h: null, victory_points: null, victory_points_threshold: null, advantage_basis: 'unknown', advantage_source: 'manager', advantage_our_pct: null, advantage_enemy_pct: null, advantage_net_pct: null, advantage_age_minutes: null, advantage_updated_at: null, contested_updated_at: null, trend: [], status_chip: 'holding' }),
]

// ---------------------------------------------------------------------------
// Campaign list items (CampaignCard)
// ---------------------------------------------------------------------------

const list_item = (over: Partial<CampaignListItem> & Pick<CampaignListItem, 'id' | 'slug' | 'name'>): CampaignListItem => ({
    short_code: 'AMA',
    tagline: 'Keep Amamake free and the complexes cycling.',
    kind: 'faction_warfare',
    status: 'active',
    start_at: iso(-12 * DAY),
    end_at: iso(16 * DAY),
    cover_image_url: '',
    systems: campaign_systems,
    areas: [],
    parties: [amarr_empire, minmatar_republic],
    structures_remaining: 0,
    structures_destroyed: 0,
    next_timer_at: null,
    enlisted: 412,
    kills: 1904,
    isk_destroyed: 128_400_000_000,
    is_enlisted: false,
    ...over,
})

export const active_faction_warfare = list_item({
    id: 1, slug: 'amamake-defense', name: 'Amamake Defense',
    parties: [amarr_empire, ...allied_parties.slice(0, 1)],
})
export const active_enlisted = list_item({
    id: 2, slug: 'auga-offensive', name: 'Auga Offensive', short_code: 'AUG',
    tagline: 'Flip Auga before downtime and hold it through the weekend.',
    is_enlisted: true,
})
export const active_strategic = list_item({
    id: 3, slug: 'snuffed-out-sovereignty', name: 'Operation Hostile Takeover', short_code: 'OHT',
    kind: 'strategic',
    tagline: 'Strip Snuffed Out of the Vard-Auga structure chain.',
    parties: [...hostile_parties, ...allied_parties],
    structures_remaining: 7, structures_destroyed: 3,
    next_timer_at: iso(26 * HOUR),
})
export const upcoming_campaign = list_item({
    id: 4, slug: 'huola-recapture', name: 'Huola Recapture', short_code: 'HUO',
    status: 'scheduled',
    tagline: 'Opens when the next warzone tick lands.',
    start_at: iso(5.5 * DAY), end_at: iso(33 * DAY),
    enlisted: 0, kills: 0, isk_destroyed: 0,
})
export const launching_campaign = list_item({
    id: 5, slug: 'vard-pickets', name: 'Vard Pickets', short_code: 'VAR',
    status: 'draft',
    start_at: iso(-HOUR), end_at: iso(14 * DAY),
    enlisted: 0, kills: 0, isk_destroyed: 0,
})
export const completed_campaign = list_item({
    id: 6, slug: 'amamake-defense-october', name: 'Amamake Defense (October)', short_code: 'AMA',
    status: 'completed',
    start_at: iso(-60 * DAY), end_at: iso(-30 * DAY),
    kills: 6120, isk_destroyed: 512_000_000_000, is_enlisted: true,
})
export const long_name_campaign = list_item({
    id: 7, slug: 'long-named-campaign',
    name: 'The Grand Combined Minmatar and Republic Fleet Joint Defense of the Heimatar and Metropolis Frontier Systems',
    tagline: 'A very long tagline that goes on to describe every single objective the leadership wants the whole alliance to understand before undocking, in a single paragraph.',
    parties: [
        party(98700010, 'The Imperial Amarrian Domain Combined Fleet Command', 'THEIMPERIAL', 'alliance', 'enemy'),
        party(98700011, 'Minmatar Republic Fleet Joint Command Allies', 'MR', 'alliance', 'ally'),
    ],
})
export const bare_campaign = list_item({
    id: 8, slug: 'bare', name: 'Bare Campaign', tagline: '', parties: [],
    cover_image_url: 'https://images.evetech.net/types/587/render?size=512',
})

// ---------------------------------------------------------------------------
// Campaign detail (CampaignEnlistBar)
// ---------------------------------------------------------------------------

export const campaign_totals: CampaignTotals = {
    enlisted: 412, kills: 1904, losses: 633, isk_destroyed: 128_400_000_000, isk_lost: 41_200_000_000,
    complexes: 288, advantage_sites: 74, advantage_generated: 5120, structure_kills: 12, capital_kills: 2,
    structures_destroyed: 3, structures_remaining: 7, active_today: 96,
}

export const campaign_detail = (over: Partial<CampaignDetail> = {}): CampaignDetail => ({
    id: 1, slug: 'amamake-defense', name: 'Amamake Defense', short_code: 'AMA',
    tagline: 'Keep Amamake free and the complexes cycling.',
    description_md: '', cover_image_url: '',
    kind: 'faction_warfare', status: 'active',
    start_at: iso(-12 * DAY), end_at: iso(16 * DAY),
    commander_order_text: '', commander_order_is_draft: false,
    systems: campaign_systems, areas: [], parties: [amarr_empire, minmatar_republic],
    structures: [], fittings: [],
    totals: campaign_totals,
    is_enlisted: false, characters_included: 0, characters_tracked: 0,
    standing_fleet_up: false, standing_fleet_members: 0, standing_fleet_boss: null,
    // The faction_warfare preset (backend campaigns.models.FEATURE_PRESETS).
    features: {
        weekly_progress: true, structures: false, timers: false, theater: true,
        fleets: true, destruction: false, pilots: true, projects: true,
    },
    paused_at: null,
    ...over,
})

// ---------------------------------------------------------------------------
// Leaderboards
// ---------------------------------------------------------------------------

const PILOTS: [number, string][] = [
    [2112954532, "Kel'dar Atram"],
    [2112954533, 'Vorlak Hegen'],
    [2112954534, 'Sabrina Thule'],
    [2112954535, 'Orin Skarsgaard'],
    [2112954536, 'Tahlia Brinn'],
    [2112954537, 'Dagr Vollmer'],
    [2112954538, 'Hesper Okonjo'],
    [2112954539, 'Ragnar Estevan'],
    [2112954540, 'Ilsa Ketterick'],
    [2112954541, 'Bjorn Aldaris'],
    [2112954542, 'Maren Quillfeather'],
    [2112954543, 'Torvald Rensfield'],
    [2112954544, 'Yara Dunmoor'],
    [2112954545, 'Cassian Verrelli'],
    [2112954546, 'Nils Heimdahl'],
    [2112954547, 'Odessa Marrowind'],
    [2112954548, 'Pelle Anscombe'],
    [2112954549, 'Rurik Valdane'],
    [2112954550, 'Sunniva Torsdal'],
    [2112954551, 'Eirik Jamaroth'],
]

export const leaderboard_rows = (count: number, top = 87): CampaignLeaderboardRow[] =>
    PILOTS.slice(0, count).map(([character_id, character_name], i) => ({
        rank: i + 1,
        user_id: 1000 + i,
        character_id,
        character_name,
        value: Math.max(1, Math.round(top * Math.pow(0.82, i))),
    }))

export const leaderboard_busy: CampaignLeaderboardRow[] = leaderboard_rows(20)
export const leaderboard_podium: CampaignLeaderboardRow[] = leaderboard_rows(3, 41)
export const leaderboard_single: CampaignLeaderboardRow[] = leaderboard_rows(1, 12)
export const leaderboard_empty: CampaignLeaderboardRow[] = []
export const leaderboard_edge: CampaignLeaderboardRow[] = [
    { rank: 1, user_id: 1, character_id: 2112954532, character_name: "Kel'dar Atram", value: 64 },
    { rank: 2, user_id: 2, character_id: null, character_name: '', value: 40 },
    { rank: 3, user_id: 3, character_id: 2112954533, character_name: 'Maximilian Bartholomew-Featherstonehaugh the Third of Heimatar', value: 31 },
    { rank: 4, user_id: 4, character_id: 2112954534, character_name: 'Zed', value: 0 },
]

export const corporation_rows: CampaignCorporationLeaderboardRow[] = [
    { rank: 1, corporation_id: 98726134, corporation_name: 'Rattini Tribe', pilots: 63, value: 482 },
    { rank: 2, corporation_id: 98700004, corporation_name: 'Republic Fleet Auxiliary', pilots: 41, value: 317 },
    { rank: 3, corporation_id: 98700020, corporation_name: 'Tribal Liberation Front Veterans', pilots: 28, value: 240 },
    { rank: 4, corporation_id: 98700021, corporation_name: 'Sebiestor Welfare Reserve', pilots: 19, value: 151 },
    { rank: 5, corporation_id: 98700022, corporation_name: 'Krusual Frontier Scouts', pilots: 12, value: 96 },
    { rank: 6, corporation_id: 98700023, corporation_name: 'Brutor Rifters Club', pilots: 7, value: 44 },
    { rank: 7, corporation_id: null, corporation_name: '', pilots: 1, value: 3 },
]

export const corporation_roster: CampaignRosterCorporation[] = [
    { corporation_id: 98726134, corporation_name: 'Rattini Tribe', pilots: 63, active_pilots: 51, characters_included: 118, kills: 612, losses: 188, isk_destroyed: 41_300_000_000, complexes: 96, advantage_sites: 24, fleets_attended: 301, last_active_day: iso(-HOUR).slice(0, 10) },
    { corporation_id: 98700004, corporation_name: 'Republic Fleet Auxiliary', pilots: 41, active_pilots: 29, characters_included: 74, kills: 388, losses: 121, isk_destroyed: 27_800_000_000, complexes: 71, advantage_sites: 18, fleets_attended: 214, last_active_day: iso(-DAY).slice(0, 10) },
    { corporation_id: 98700020, corporation_name: 'Tribal Liberation Front Veterans', pilots: 28, active_pilots: 6, characters_included: 33, kills: 140, losses: 71, isk_destroyed: 9_100_000_000, complexes: 22, advantage_sites: 3, fleets_attended: 88, last_active_day: iso(-6 * DAY).slice(0, 10) },
    { corporation_id: null, corporation_name: '', pilots: 2, active_pilots: 0, characters_included: 2, kills: 0, losses: 0, isk_destroyed: 0, complexes: 0, advantage_sites: 0, fleets_attended: 0, last_active_day: null },
]

// ---------------------------------------------------------------------------
// Sites
// ---------------------------------------------------------------------------

const site = (i: number, over: Partial<CampaignSite>): CampaignSite => ({
    id: i,
    occurred_at: iso(-i * 47 * 60_000),
    site_kind: 'complex',
    amount_lp: 0,
    system: 'Amamake',
    character_id: PILOTS[i % PILOTS.length][0],
    character_name: PILOTS[i % PILOTS.length][1],
    plex_class: '',
    plex_size: '',
    confidence: '',
    ...over,
})

export const sites_typical: CampaignSite[] = [
    site(1, { system: 'Amamake', plex_size: 'Medium', amount_lp: 36_000, plex_class: 'Defensive', confidence: 'high' }),
    site(2, { system: 'Auga', plex_size: 'Small', amount_lp: 9_000, plex_class: 'Offensive', confidence: 'medium' }),
    site(3, { system: 'Huola', site_kind: 'advantage_site' }),
    site(4, { system: 'Vard', site_kind: 'propaganda_beacon' }),
    site(5, { system: 'Amamake', site_kind: 'rendezvous_point' }),
    site(6, { system: 'Auga', site_kind: 'supply_cache' }),
    site(7, { system: 'Huola', site_kind: 'listening_outpost' }),
    site(8, { system: 'Vard', site_kind: 'battlefield' }),
    site(9, { system: 'Amamake', amount_lp: 1_240, confidence: 'low' }),
]

export const sites_busy: CampaignSite[] = Array.from({ length: 25 }, (_, i) =>
    site(i + 1, i % 3 === 0
        ? { system: ['Amamake', 'Auga', 'Huola', 'Vard'][i % 4], site_kind: 'advantage_site' }
        : { system: ['Amamake', 'Auga', 'Huola', 'Vard'][i % 4], plex_size: ['Small', 'Medium', 'Large'][i % 3], amount_lp: [9_000, 36_000, 90_000][i % 3], plex_class: 'Defensive', confidence: 'high' }))

export const sites_edge: CampaignSite[] = [
    site(1, { character_id: null, character_name: '', site_kind: 'unmapped_site_kind', system: 'Amamake' }),
    site(2, { character_name: 'Maximilian Bartholomew-Featherstonehaugh the Third of Heimatar', plex_size: 'Large', amount_lp: 90_000 }),
]

// ---------------------------------------------------------------------------
// Structures
// ---------------------------------------------------------------------------

const structure = (id: number, over: Partial<CampaignStructure>): CampaignStructure => ({
    id,
    name: `Amamake - Structure ${id}`,
    structure_type: 'astrahus',
    type_id: null,
    solar_system_id: 30002537,
    system_name: 'Amamake',
    corporation_id: 98700001,
    corporation_name: 'Clan Vanguard of Amarr',
    alliance_id: 99002685,
    alliance_name: 'Snuffed Out',
    related_alliance_id: null,
    related_alliance_name: '',
    owner_alliance_id: 99002685,
    owner_alliance_ticker: 'SNUFF',
    affiliation: 'hostile',
    status: 'anchored',
    source: 'recon',
    fitting: '',
    reinforce_hour: null,
    timer_id: null,
    timer_at: null,
    destroyed_at: null,
    killmail_id: null,
    ...over,
})

export const structures_typical: CampaignStructure[] = [
    structure(1, { name: 'Amamake - Freeport', structure_type: 'azbel', affiliation: 'friendly', corporation_name: 'Rattini Tribe', alliance_name: 'Minmatar Fleet Alliance', owner_alliance_id: 99011978, owner_alliance_ticker: 'MINMATAR', fitting: 'Market + Cap Ship Assembly' }),
    structure(2, { name: 'Auga - Forward Keep', structure_type: 'fortizar', system_name: 'Auga', solar_system_id: 30002542, status: 'reinforced', reinforce_hour: 18, timer_at: iso(30 * HOUR), related_alliance_name: 'Clan Vanguard of Amarr', fitting: 'Doomsday' }),
    structure(3, { name: 'Vard - Jump Gate', structure_type: 'ansiblex_jump_gate', system_name: 'Vard', solar_system_id: 30002538, status: 'anchored', reinforce_hour: 3 }),
    structure(4, { name: 'Huola - Old Keep', structure_type: 'astrahus', system_name: 'Huola', solar_system_id: 30003067, status: 'destroyed', destroyed_at: iso(-2 * DAY), killmail_id: 123456789 }),
    structure(5, { name: 'Amamake - Moon Drill', structure_type: 'metenox_moon_drill', affiliation: 'neutral', corporation_name: '', alliance_name: '', owner_alliance_id: null, owner_alliance_ticker: '', status: 'unanchored' }),
]

export const structures_single: CampaignStructure[] = [structures_typical[1]]

export const structures_busy: CampaignStructure[] = Array.from({ length: 14 }, (_, i) =>
    structure(i + 10, {
        name: `${['Amamake', 'Auga', 'Huola', 'Vard'][i % 4]} - Citadel ${i + 1}`,
        system_name: ['Amamake', 'Auga', 'Huola', 'Vard'][i % 4],
        structure_type: ['astrahus', 'raitaru', 'athanor', 'tatara', 'azbel'][i % 5],
        affiliation: (['hostile', 'friendly', 'neutral'] as const)[i % 3],
        status: (['anchored', 'reinforced', 'destroyed', 'unanchored'] as const)[i % 4],
        reinforce_hour: i % 2 === 0 ? (i * 3) % 24 : null,
        timer_at: i % 4 === 1 ? iso((i + 3) * HOUR) : null,
        destroyed_at: i % 4 === 2 ? iso(-i * HOUR) : null,
        fitting: i % 5 === 0 ? 'Standup fit' : '',
    }))

export const structures_edge: CampaignStructure[] = [
    structure(30, {
        name: 'Amamake - A Structure With An Extraordinarily Long Name That Keeps Going And Going',
        corporation_name: 'The Imperial Amarrian Domain Combined Fleet Command Holdings',
        related_alliance_name: 'Minmatar Republic Fleet Joint Command Allies International',
        reinforce_hour: 0,
        timer_at: iso(4 * HOUR),
    }),
    structure(31, { name: 'Unknown Deployable', structure_type: 'mystery_deployable', type_id: 35840 }),
]

// ---------------------------------------------------------------------------
// Fittings
// ---------------------------------------------------------------------------

const fitting = (id: number, order: number, ship_name: string, role_label: string, srp_eligible = true, fitting_id = 9000 + id): CampaignFitting => ({
    id, fitting_id, name: `${ship_name} - ${role_label || 'Fleet'}`, ship_name, role_label, srp_eligible, order,
})

export const fittings_typical: CampaignFitting[] = [
    fitting(1, 1, 'Hurricane Fleet Issue', 'DPS'),
    fitting(2, 2, 'Scimitar', 'Logistics'),
    fitting(3, 3, 'Sabre', 'Interdictor', false),
    fitting(4, 4, 'Rifter', 'Academy Frigate'),
    fitting(5, 5, 'Vagabond', ''),
]

export const fittings_single: CampaignFitting[] = [fitting(1, 1, 'Stabber Fleet Issue', 'Logi Anchor')]

export const fittings_edge: CampaignFitting[] = [
    fitting(1, 1, 'Typhoon', 'Doctrine Battleship With A Remarkably Long Role Label Nobody Asked For'),
    fitting(2, 2, 'Muninn', '', true),
    { id: 3, fitting_id: 0, name: 'Broken link', ship_name: 'Ghost', role_label: 'Hidden because no fitting id', srp_eligible: true, order: 3 },
]

// ---------------------------------------------------------------------------
// SystemCard
// ---------------------------------------------------------------------------

export const system_cards: Record<string, SystemCardInfo> = {
    amamake: { system_name: 'Amamake', system_id: 30002537, sun_type_id: 3802, distance_yl: 0, region_name: 'Heimatar', constellation_name: 'Hed', security: 0.4388, moons_count: 11, progress: 61 },
    auga: { system_name: 'Auga', system_id: 30002542, sun_type_id: 45039, distance_yl: 0.42, region_name: 'Heimatar', constellation_name: 'Hed', security: 0.3855, moons_count: 7, progress: 78 },
    huola: { system_name: 'Huola', system_id: 30003067, sun_type_id: 3803, distance_yl: 6.18, region_name: 'The Bleak Lands', constellation_name: 'Sasen', security: 0.3702, moons_count: 0, progress: 24 },
    vard: { system_name: 'Vard', system_id: 30002538, sun_type_id: 3801, distance_yl: 1.07, region_name: 'Heimatar', constellation_name: 'Hed', security: 0.3791, moons_count: 4, progress: 0 },
    lowsec_edge: { system_name: 'Old Man Star', system_id: 30005000, sun_type_id: 3802, distance_yl: 12.5, region_name: 'Essence', constellation_name: 'Vieres', security: 0.3357, moons_count: 3, progress: 100 },
}

// ---------------------------------------------------------------------------
// CampaignStatBar
// ---------------------------------------------------------------------------

export const stat_bar_stats: CampaignStat[] = [
    { label: 'Pilots', value: '412', title: 'Enlisted pilots' },
    { label: 'Kills', value: '1,904' },
    { label: 'Losses', value: '633' },
    { label: 'ISK destroyed', value: '128.4b', title: '128,400,000,000 ISK' },
    { label: 'Complexes', value: '288' },
    { label: 'Active today', value: '96' },
]
