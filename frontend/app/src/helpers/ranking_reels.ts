import type {
    FleetCommanderMetrics,
    IndustryOrderCharacterStatistics,
    MarketOperatorStatistics,
    SpaceTruckerStatistics,
} from '@dtypes/api.minmatar.org'
import type { useTranslations, useTranslatedPath } from '@i18n/utils'
import { formatIskCompact } from '@/data/industry/guide-order-summary'
import { format_isk } from '@helpers/numbers'

type T = ReturnType<typeof useTranslations>
type TranslatePath = ReturnType<typeof useTranslatedPath>

/** One leaderboard entry; the stat line is already formatted by the reel that owns it. */
export interface RankedPilotItem {
    character_id:   number;
    character_name: string;
    stat_text:      string;
}

/** Props for RankingReel: the bottom-bar leaderboard strip on the fleet, freight, industry and market hubs. */
export interface RankingReelProps {
    title:          string;
    caption:        string;
    /** Width of the title column. */
    fixed_width:    string;
    items:          RankedPilotItem[];
    /** Optional call to action shown after the pilots. */
    cta?:           { href: string; text: string };
}

const SUPPLY_TRIBE_PATH = '/alliance/tribes/?tribe=supply'
const MARKET_TRIBE_PATH = '/alliance/tribes/?tribe=market'

export function fleet_commanders_reel(rows: FleetCommanderMetrics[], t: T): RankingReelProps {
    return {
        title: t('fleet_commanders_ranking'),
        caption: t('current_calendar_month'),
        fixed_width: '210px',
        items: rows.map(row => ({
            character_id: row.primary_character_id ?? 0,
            character_name: row.primary_character_name ?? '',
            stat_text: t(row.fleet_count != 1 ? 'fleets_plural' : 'fleets_singular').replace('{count}', String(row.fleet_count)),
        })),
    }
}

export function space_truckers_reel(rows: SpaceTruckerStatistics[], t: T, translate_path: TranslatePath): RankingReelProps {
    return {
        title: t('space_trucker_ranking'),
        caption: t('last_30_days'),
        fixed_width: '170px',
        items: rows.map(row => ({
            character_id: row.primary_character_id ?? 0,
            character_name: row.primary_character_name ?? '',
            stat_text: t(row.completed_contracts_count != 1 ? 'contracts_plural' : 'contracts_singular').replace('{count}', String(row.completed_contracts_count)),
        })),
        cta: { href: translate_path(SUPPLY_TRIBE_PATH), text: t('become_a_trucker') },
    }
}

// The two ISK reels still use different compact formatters (2 decimals vs FD-10's shared format_isk); kept as-is so the
// rendered numbers don't change here. Swap formatIskCompact for the shared formatter when FD-10 lands.
export function industry_manufacturers_reel(rows: IndustryOrderCharacterStatistics[], t: T, translate_path: TranslatePath): RankingReelProps {
    return {
        title: t('industry_manufacturer_ranking'),
        caption: t('last_30_days'),
        fixed_width: '170px',
        items: rows.map(row => ({
            character_id: row.primary_character_id ?? 0,
            character_name: row.primary_character_name ?? '',
            stat_text: `${formatIskCompact(Number(row.delivered_isk_estimate))} ${t('isk')}`,
        })),
        cta: { href: translate_path(SUPPLY_TRIBE_PATH), text: t('become_a_supplier') },
    }
}

export function market_operators_reel(rows: MarketOperatorStatistics[], t: T, translate_path: TranslatePath): RankingReelProps {
    return {
        title: t('market_operator_ranking'),
        caption: t('currently_on_market'),
        fixed_width: '170px',
        items: rows.map(row => ({
            character_id: row.primary_character_id ?? 0,
            character_name: row.primary_character_name ?? '',
            stat_text: t('market_operator_isk_on_market').replace('{isk}', format_isk(row.total_isk_on_market)),
        })),
        cta: { href: translate_path(MARKET_TRIBE_PATH), text: t('join_market') },
    }
}
