import {
    AAR_URL as KAMELA_AAR_URL,
    CAMPAIGN_ISK_DESTROYED as KAMELA_BRAWL_ISK,
    REVELATIONS_LOST as KAMELA_REVELATIONS,
    SHIPS_DESTROYED as KAMELA_BRAWL_SHIPS,
} from '@/data/campaigns/kamela'

import type { AmamakeMarketIssue, MarketStat } from './types'
import {
    AMAMAKE,
    CAPITAL_SPLIT,
    CATCHMENT,
    CATEGORIES,
    DAYS,
    DAYS_IN_MONTH,
    HUB_HEALTH,
    HULLS,
    HULLS_LOST_TOTAL,
    HULLS_SOLD_TOTAL,
    INDUSTRY_AS_OF,
    INDUSTRY_INDICES,
    PIPE,
    REGIONS,
    SALES_TOTALS,
    SALES_TOTALS_VS,
    TOP_TYPES,
    WARZONE,
    WEEKS,
} from './yc128-08-boards'

export const SLUG = 'yc128-08' as const
export const PERMALINK_PATH = `/amamake-market/${SLUG}/` as const
export const COVER_IMAGE = '/images/home-amamake-cover.jpg'

const n = (value: number) => value.toLocaleString('en-US')
const isk = (value: number) => {
    if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 100_000_000_000) return `${Math.round(value / 1_000_000_000)}B`
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
    return `${(value / 1_000_000).toFixed(0)}M`
}
const day = (date: string) => {
    const d = new Date(`${date}T00:00:00Z`)
    return `${d.getUTCDate()} ${d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`
}
const pct_word = (pct: number | null) =>
    pct === null ? 'with no July baseline' : pct >= 0 ? `up ${pct}% on July` : `down ${Math.abs(pct)}% on July`

const category = (name: string) => CATEGORIES.find((row) => row.name === name)
const split = (system: string) => CAPITAL_SPLIT.find((row) => row.system === system)
const kamela = split('Kamela')
const amamake_split = split('Amamake')
const days_missing = DAYS_IN_MONTH - SALES_TOTALS.days_with_sales

const shelf_stats: MarketStat[] = []
if (HUB_HEALTH?.sell_orders_isk) {
    shelf_stats.push({ label: 'On sell orders', value: isk(HUB_HEALTH.sell_orders_isk), note: 'live book, all sellers' })
}
if (HUB_HEALTH?.contracts_isk) {
    shelf_stats.push({ label: 'On public contracts', value: isk(HUB_HEALTH.contracts_isk), note: 'fitted hulls, live' })
}
if (HUB_HEALTH?.sell_orders_health_pct != null) {
    shelf_stats.push({ label: 'Sells within markup of Jita', value: `${Math.round(HUB_HEALTH.sell_orders_health_pct)}%`, note: 'tracked doctrine types' })
}
if (HUB_HEALTH?.contracts_health_pct != null) {
    shelf_stats.push({ label: 'Doctrine contract coverage', value: `${Math.round(HUB_HEALTH.contracts_health_pct)}%` })
}

export const YC128_08: AmamakeMarketIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    cover_image: COVER_IMAGE,
    published_at: new Date('2026-08-31T00:00:00Z'),
    period_utc: '1–31 Aug 2026 UTC',
    previous_period_label: 'July',
    context_as_of: INDUSTRY_AS_OF,
    headline: 'Kamela ate capitals. Amamake sold destroyers.',
    focus_name: 'Kamela’s capitals',
    opening: [
        'Hello sales tax enjoyers. This structure is still sixth on Fuzzwork by sell orders, behind Jita, Amarr, Dodixie, Hek, and Rens. CCP does not publish structure transactions; we watch the order book move about every fifteen minutes and treat every total on this page as a floor. Amarr dock here. Gallente and Caldari hulls sell here. This is a freeport on the warzone, not an alliance ledger.',
        `${SALES_TOTALS.isk_label} ISK moved through the book in August across ${n(SALES_TOTALS.fills)} inferred fills and ${n(SALES_TOTALS.types)} types, ${pct_word(SALES_TOTALS_VS.isk_pct)}. Money moved in ${CATEGORIES[0]?.name.toLowerCase()} (${CATEGORIES[0]?.isk_label}) and ${CATEGORIES[1]?.name.toLowerCase()} (${CATEGORIES[1]?.isk_label}); charges were ${category('Charges')?.isk_label ?? '—'} and ${n(category('Charges')?.units ?? 0)} units, which is the plexing ammo. The warzone around the shop lost ${n(WARZONE.ships)} ships and ${WARZONE.isk_label} ISK. Amamake was ${AMAMAKE.share_of_warzone}% of those ships.`,
        `What made August different is not the shop. Kamela ate ${kamela?.capital_ships ?? 0} capitals while this undock ate Typhoons, and ${day(AMAMAKE.loudest_day.date)} was a local meat grinder, not a region-wide node. That is the focus of the month.`,
    ],

    sales: SALES_TOTALS,
    sales_vs: SALES_TOTALS_VS,
    days: DAYS,
    weeks: WEEKS,
    weeks_dek:
        'Quiet days still clear tens of billions: ammo, paste, and people who live here. Inventory for the floor. Make margin on the spikes.',
    weeks_footnote: [
        `Inferred ISK sold at the freeport, by day and by calendar week of August 2026.`,
        SALES_TOTALS.loudest_day
            ? `Loudest day ${day(SALES_TOTALS.loudest_day.date)} at ${isk(SALES_TOTALS.loudest_day.isk)} on ${n(SALES_TOTALS.loudest_day.fills)} fills.`
            : '',
        days_missing > 0
            ? `Hatched columns are ${days_missing} days with no order-book snapshots; the month total is a floor.`
            : '',
        'Order-book diffs, roughly fifteen-minute snapshots.',
    ]
        .filter(Boolean)
        .join(' '),
    categories: CATEGORIES,

    top_types: {
        rows: TOP_TYPES,
        dek: 'Rank by units and Tritanium, Pyerite, and Hail always look like the story. Rank by ISK and the hub is injectors, paste, T2 rigs, and the destroyers that die on the undock.',
        footnote: `Top types by inferred ISK (quantity times fill price), August 2026, Amamake structure. Percentages are the type's share of the month and its change on July. A single-fill hull or blueprint copy can be one buyer; treat it as noise until a second month shows it again.`,
    },

    hulls: {
        rows: HULLS,
        dek: 'Hulls lost in Amamake against inferred sells of the same hull. Tackle sells about as fast as it dies. Where the ratio drops below one, the shelf is being drained by the undock, and that is where an importer or a builder starts next month.',
        footnote: `August counts. Sells: inferred fills at the freeport. Losses: killmails in Amamake (30002537) only, capsules excluded. Ranked by sold plus lost; across every hull type ${n(HULLS_SOLD_TOTAL)} were sold here and ${n(HULLS_LOST_TOTAL)} were lost here.`,
    },

    catchment: {
        amamake: AMAMAKE,
        warzone: WARZONE,
        rows: CATCHMENT,
        regions: REGIONS,
        pipe: PIPE,
        dek: [
            `We watch ${WARZONE.systems} Amarr–Minmatar systems. Amamake is the shop and a pipe, so it will usually lead. The Heimatar run (${PIPE.label}) lost ${n(PIPE.ships)} ships this month, ${PIPE.share}% of the warzone. Kourmonen is still the volume system in The Bleak Lands. About ${n(AMAMAKE.unique_characters)} characters showed up on Amamake killmails. That is whoever flew the pipe, not a corporation.`,
            'Occupancy is a snapshot, not a monthly average. Amamake itself was Minmatar-held and quiet: dock, buy, leave. The loud systems were the ones being taken. Shop in the quiet ones. Plex in the loud ones.',
        ],
        footnote: `Ships destroyed, August 2026, ${WARZONE.systems} monitored systems, capsules and NPC-only kills removed, from the same zKillboard pass as the Warzone Report. Holder marks are the live ESI occupier. Capital ISK is the share of a system's destroyed ISK that was capital hulls.`,
    },

    focus: {
        title: 'Kamela’s capitals, Amamake’s Typhoons',
        window_label: 'August · Kamela and Amamake',
        section_dek: 'One story that would not fit a normal issue: the month the expensive ships died one jump off the shop, not on it.',
        dek: [
            `On ${day(AMAMAKE.loudest_day.date)}, Amamake lost ${n(AMAMAKE.loudest_day.ships)} ships. It was the loudest market day of the month too, and it was a weekday in Heimatar, not a nullsec CTA.`,
            `If you only watch this undock you will think expensive ships die here. They do not, relatively. Kamela was outside the top five for ships lost and second in ISK destroyed. ${kamela?.capital_ships ?? 0} capitals left the field there, ${KAMELA_REVELATIONS} of them Revelations, plus a wall of Tempest Fleet Issues. Those hulls are ${kamela?.capital_isk_label ?? '—'} of Kamela's ISK. Amamake lost ${amamake_split?.capital_ships ?? 0} capitals, including a Nyx, and that is still only about a third of the ${AMAMAKE.isk_label} that died in system. Dal, the occupancy fight, is almost all subcaps.`,
        ],
        stats: [
            { label: 'Kamela capitals lost', value: n(kamela?.capital_ships ?? 0), note: kamela?.capital_isk_label ? `${kamela.capital_isk_label} ISK` : undefined },
            { label: 'Amamake capitals lost', value: n(AMAMAKE.capital_ships), note: `${isk(AMAMAKE.capital_isk)} of ${AMAMAKE.isk_label}` },
            { label: 'Loudest Amamake day', value: day(AMAMAKE.loudest_day.date), note: `${n(AMAMAKE.loudest_day.ships)} ships` },
            { label: 'Kamela Fortizar brawl', value: isk(KAMELA_BRAWL_ISK), note: `${n(KAMELA_BRAWL_SHIPS)} ships on 29 Aug` },
        ],
        capital_split: CAPITAL_SPLIT,
        capital_split_footnote:
            'ISK destroyed by system, August 2026, zKillboard totalValue. Capitals are dreadnoughts, carriers, supercarriers, titans, force auxiliaries, capital industrials, and jump freighters; everything else is subcap.',
        closing: [
            `There was a ${isk(KAMELA_BRAWL_ISK)} afternoon in Kamela at the end of the month. Do not restock Amamake as if it happened on this undock. What died one jump off the shop was Typhoons, Abaddons, and Hyperions. Dropping a FAX in known space is usually a statement, escalate or die, and Kamela spent August doing that. This hub spent August selling destroyers.`,
        ],
        cta_label: 'AAR: 350B down in Kamela (29 Aug)',
        cta_href: KAMELA_AAR_URL,
    },

    import_vs_local: {
        dek: [
            'Same goal as March: things that actually move, under 20% of Jita after freight. Jita to Amamake is 450 ISK/m³ packaged. Fleet Issue destroyers are already here. Typhoons are not. Hail and Republic Fleet EMP print Jita, so that is a pickup, not a jump freighter.',
        ],
        table: {
            headers: ['Type', 'Amamake', 'Jita', 'Freight in', 'Call'],
            rows: [
                { cells: ['Thrasher Fleet Issue', '16.8M', '17.5M', '1.1M', 'Skip'], tone: 'success' },
                { cells: ['Hurricane Fleet Issue', '122.8M', '124.2M', '6.8M', 'Skip'], tone: 'success' },
                { cells: ['Hecate', '83.6M', '85.4M', '2.3M', 'Skip'], tone: 'success' },
                { cells: ['Stabber Fleet Issue', '40.1M', '40.1M', '4.5M', 'Skip'], tone: 'success' },
                { cells: ['Typhoon', '195.0M', '170.5M', '22.5M', 'Haul'], tone: 'info' },
                { cells: ['Nanite Repair Paste', '28.2k', '28.1k', '~0', 'Even'] },
                { cells: ['Hail M / RF EMP S', 'Jita print', 'Jita print', '~0', 'Pickup'] },
            ],
            footnote:
                'Lowest Amamake sell versus the Jita average on 31 Aug, after 450 ISK/m³ freight (destroyer 2,500 m³, tactical destroyer 5,000, cruiser 10,000, battlecruiser 15,000, battleship 50,000). Skip: local is already cheaper. Haul: Jita plus freight still wins. Hand-collected month-end snapshot.',
        },
    },

    industry: {
        dek: [
            'Sotiyo and Tatara, faction warfare level 5, 0.75% facility tax. The system cost index is high because the system is busy; the −50% rebate is why you still job here. Refine and T1 in Amo. Keep reactions off Auner. Do not job in Auga: cheap index, no buyers.',
            'Thrasher Fleet Issue, Stabber, Exequror and Vexor Navy, and Hurricane Fleet Issue cleared at or under Jita. Typhoons did not. Build the first group. Import the second. Industry legs from Amo, Auner, and Basgerin are 120 ISK/m³; the 450 pipe is for the haul column.',
        ],
        indices: INDUSTRY_INDICES,
        footnote: `ESI system cost indices as of ${INDUSTRY_AS_OF}. Indices move daily with job volume, so read the shape, not the third decimal.`,
    },

    loyalty: {
        dek: [
            'Public store math only. Convert TLIB or 24th Imperial into hulls this book already sells. Do not chase paper ISK/LP on day one, and do not haul the output in an Iteron. The offers tool works for any faction. Plex in the loud systems above; job and sell here.',
        ],
        table: {
            headers: ['Offer', 'Militia', 'ISK/LP', '30d vol'],
            rows: [
                { cells: ['Imperial Navy 200mm Steel Plates', '24th', '1,175', '1.1k'] },
                { cells: ['Republic Fleet Target Painter', 'TLIB', '1,013', '2.4k'] },
                { cells: ['Imperial Navy Infiltrator', '24th', '979', '39k'] },
                { cells: ['Stabber Fleet Issue BPC', 'TLIB', '899', '1.5k'] },
                { cells: ['Republic Fleet Berserker', 'TLIB', '876', '30.8k'] },
                { cells: ['Omen Navy Issue BPC', '24th', '930', '1.6k'] },
            ],
            footnote:
                'Buy conversion on 31 Aug, corporations 1000182 (Tribal Liberation Force) and 1000179 (24th Imperial Crusade). Amarr plates lead on rate; TLIB painters and Fleet BPCs lead on volume into this hub. Hand-collected month-end snapshot.',
        },
        actions: [
            { href: '/learning/guides/selling-loyalty-points/', label: 'LP cashout guide' },
            { href: '/industry/loyalty/offers/', label: 'LP offers (any faction)' },
        ],
    },

    shelf: {
        dek: [
            'Nanite around 28,000 with hundreds of thousands on the shelf. Hail is a pickup. Thrasher Fleet Issue under 17 million. Typhoon around 195 million and thin. We do not list which fittings are empty; the public sell-orders page already shows what is low.',
            'You can undock a fitted destroyer without a hauler alt. Travel to Amamake, buy the ship, pick a small complex off the Agency window. The book does not check your militia.',
        ],
        stats: shelf_stats,
        actions: [
            { href: '/market/ops/sell_orders/', label: 'Sell orders' },
            { href: 'https://market.fuzzwork.co.uk/station/1022167642188/', label: 'Fuzzwork station book' },
            { href: `https://zkillboard.com/system/${AMAMAKE.system_id}/`, label: 'zKill Amamake' },
            { href: 'https://www.reddit.com/r/Eve/comments/1rhy941/how_minmatar_fleet_uses_esi_to_support_multiple/', label: 'How we run the markets (Mar YC128)' },
        ],
    },

    get_involved: {
        steps: [
            {
                title: 'Buy here',
                text: 'Every doctrine hull and fit is on the shelf or on contract. Check the public book before you haul anything from Jita.',
                href: '/market/ops/sell_orders/',
                label: 'Browse the sell orders',
            },
            {
                title: 'Sell here',
                text: 'List at or under Jita plus freight and it moves. Fleet Issue destroyers, navy cruisers, paste, and ammo cleared all month; battleships did not.',
                href: '/market/ops/contracts/',
                label: 'Doctrine contracts',
            },
            {
                title: 'Build here',
                text: 'Faction warfare level 5 gives the −50% index rebate. Refine in Amo, react anywhere but Auner, and job the hulls in the died-vs-sold table that sold under Jita.',
                href: '/industry/',
                label: 'Industry hub',
            },
        ],
        actions: [{ href: 'https://discord.com/invite/3hZfahmkFx', label: 'Join Militia Discord' }],
        featured_guides: ['selling-loyalty-points', 'navy-destroyer-metagame', 'navy-frigate-guide'],
    },

    methodology: [
        {
            label: 'Inferred fills',
            text: 'CCP does not publish structure transactions. Minmatar Fleet snapshots the Amamake sell book about every fifteen minutes and records each drop in an order as a fill at that order\'s price. ISK sold is quantity times fill price, summed over the calendar month (UTC). Buy orders, relists and cancelled orders are not counted, so every total is a floor.',
        },
        {
            label: 'Month over month',
            text: 'Deltas compare the same measure against the prior calendar month from the same snapshot feed.',
        },
        {
            label: 'Died vs sold',
            text: 'Hull losses are killmails in the Amamake system only, capsules excluded, matched by type to inferred sells of the same hull at the structure.',
        },
        {
            label: 'Destruction',
            text: 'Every ship kill in the Amarr–Minmatar faction-warfare systems for the month, from zKillboard, with capsules and NPC-only kills removed. Identical to the Warzone Report for the same month.',
        },
        {
            label: 'Live context',
            text: `Industry cost indices and hub-health figures are live snapshots from ESI and the Minmatar Fleet API, dated ${INDUSTRY_AS_OF}. The import and loyalty tables are hand-collected at month end.`,
        },
        {
            label: 'Not shown',
            text: 'No operator names, no per-seller volumes, no empty-fitting list, and no live hull depth. The public sell-orders page shows what is low.',
        },
    ],
}
