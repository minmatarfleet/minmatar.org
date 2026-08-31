import {
    format_hours,
    format_isk,
    format_volume_m3,
} from '@helpers/numbers'
import { ui } from '@i18n/ui'

export type TribeActivityMetric = {
    label: string
    value: string
}

type Translate = (key: keyof typeof ui['en']) => string

export type TribeActivitySpec = {
    metrics: (
        t: Translate,
        totals: Record<string, number | string>,
    ) => TribeActivityMetric[]
}

function total_number(
    totals: Record<string, number | string>,
    key: string,
): number {
    const raw = totals[key]
    const parsed = typeof raw === 'number' ? raw : Number(raw)
    return Number.isFinite(parsed) ? parsed : 0
}

export const TRIBE_ACTIVITY_BY_CODE: Record<string, TribeActivitySpec> = {
    'supply.mining': {
        metrics: (t, totals) => [
            {
                label: t('tribes.activity.mining.miner_count'),
                value: String(total_number(totals, 'miner_count')),
            },
            {
                label: t('tribes.activity.mining.total_volume_m3'),
                value: `${format_volume_m3(total_number(totals, 'total_volume_m3'))} m³`,
            },
            {
                label: t('tribes.activity.mining.total_isk_ore_market_estimate'),
                value: `${format_isk(total_number(totals, 'total_isk_ore_market_estimate'))} ISK`,
            },
            {
                label: t('tribes.activity.mining.avg_isk_per_character'),
                value: `${format_isk(total_number(totals, 'avg_isk_per_character'))} ISK`,
            },
        ],
    },
    'supply.freighters': {
        metrics: (t, totals) => [
            {
                label: t('tribes.activity.freighters.avg_completion_hours'),
                value: `${format_hours(total_number(totals, 'avg_completion_hours'))}h`,
            },
            {
                label: t('tribes.activity.freighters.median_completion_hours'),
                value: `${format_hours(total_number(totals, 'median_completion_hours'))}h`,
            },
            {
                label: t('tribes.activity.freighters.total_volume_m3'),
                value: `${format_volume_m3(total_number(totals, 'total_volume_m3'))} m³`,
            },
            {
                label: t('tribes.activity.freighters.avg_volume_per_contract'),
                value: `${format_volume_m3(total_number(totals, 'avg_volume_per_contract'))} m³`,
            },
        ],
    },
}
