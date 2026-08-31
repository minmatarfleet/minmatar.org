/** Frozen Amamake Market Report · August YC128. No live fetch. */

import type { CampaignTableRow } from '@/data/campaigns/etherium-reach'

export const PERIOD_LABEL = '1–31 Aug YC128'
export const CUTOFF_NOTE =
    'Fills and killmails through 12:05 UTC on 31 Aug (partial last day). Occupancy is the 31 Aug 12:03 snapshot.'

export const ZKILL_AMA = 'https://zkillboard.com/system/30002537/'
export const FUZZWORK_STATION = 'https://market.fuzzwork.co.uk/station/1022167642188/'
export const ESI_MARKETS =
    'https://www.reddit.com/r/Eve/comments/1rhy941/how_minmatar_fleet_uses_esi_to_support_multiple/'
export const KAMELA_AAR =
    'https://www.reddit.com/r/Eve/comments/1w21ozl/aar_350b_down_in_kamela/'
export const SELL_ORDERS_PATH = '/market/sell-orders/'
export const LP_OFFERS_PATH = '/industry/loyalty/offers/'
export const LP_GUIDE_PATH = '/learning/guides/selling-loyalty-points/'

export const ISK_SOLD = 1_224_512_972_344
export const ISK_SOLD_VS_JULY = 0.15
export const AMA_KILLS = 10_469
export const HUB_HEALTH = 0.72
export const AUG_FILLS = 163_137
export const AUG_TYPES = 2_842
export const AUG_UNITS = 169_659_644
export const AMA_UNIQUE = 4_549
export const AMA_DESTROYED = 896_300_000_000
export const WZ_KILLS = 52_110
export const WZ_DESTROYED = 3_860_000_000_000
export const PIPE_KILLS = 23_760

export const WEEK_CATS = ['1–7 Aug', '8–14', '15–21', '22–28', '29–31']
export const WEEK_ISK_B = [279.0, 266.0, 304.8, 262.0, 112.7]

export const VOL_CATS = [
    'Amamake',
    'Kourmonen',
    'Auga',
    'Siseide',
    'Dal',
    'Kamela',
    'Vard',
    'Aset',
]
export const VOL_KILLS = [10469, 4520, 3679, 3050, 3039, 2897, 2361, 2002]

export const CAP_CATS = ['Amamake', 'Kamela', 'Kourmonen', 'Dal', 'Turnur', 'Huola']
export const CAP_ISK_B = [280.2, 272.4, 35.8, 13.1, 49.1, 53.5]
export const SUB_ISK_B = [616.2, 216.6, 255.8, 162.9, 91.4, 57.8]

export const SOLD_CATS = [
    'LSI',
    'Nanite',
    'Hecate',
    'Bulkhead II',
    'TFI',
    'Helium',
    'Extractor',
    'Navy Cap 3200',
]
export const SOLD_ISK_B = [29.89, 20.67, 15.73, 12.28, 10.96, 10.96, 10.52, 10.35]

export const DIED_CATS = [
    'Rifter',
    'TFI',
    'Tristan',
    'Thrasher',
    'Slasher',
    'Comet',
    'Punisher',
    'Slicer',
]
export const DIED_SOLD = [1070, 600, 494, 479, 472, 392, 379, 305]
export const DIED_LOST = [797, 300, 266, 293, 213, 218, 207, 198]

export const IMPORT_ROWS: CampaignTableRow[] = [
    { cells: ['Thrasher Fleet Issue', '16.8M', '17.5M', '1.1M', 'Skip'] },
    { cells: ['Hurricane Fleet Issue', '122.8M', '124.2M', '6.8M', 'Skip'] },
    { cells: ['Hecate', '83.6M', '85.4M', '2.3M', 'Skip'] },
    { cells: ['Stabber Fleet Issue', '40.1M', '40.1M', '4.5M', 'Skip'] },
    { cells: ['Typhoon', '195.0M', '170.5M', '22.5M', 'Haul'] },
    { cells: ['Nanite Repair Paste', '28.2k', '28.1k', '~0', 'Even'] },
    { cells: ['Hail M / RF EMP S', 'Jita print', 'Jita print', '~0', 'Pickup'] },
]

export const LP_ROWS: CampaignTableRow[] = [
    { cells: ['Imperial Navy 200mm Steel Plates', '24th', '1,175', '1.1k'] },
    { cells: ['Republic Fleet Target Painter', 'TLIB', '1,013', '2.4k'] },
    { cells: ['Imperial Navy Infiltrator', '24th', '979', '39k'] },
    { cells: ['Stabber Fleet Issue BPC', 'TLIB', '899', '1.5k'] },
    { cells: ['Republic Fleet Berserker', 'TLIB', '876', '30.8k'] },
    { cells: ['Omen Navy Issue BPC', '24th', '930', '1.6k'] },
]

export const FOCUS_TITLE = "Kamela's capitals, Amamake's Typhoons"
