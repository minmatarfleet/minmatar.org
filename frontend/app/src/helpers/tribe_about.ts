import {
    format_isk,
    format_number,
    number_thousand_separator,
} from '@helpers/numbers'
import type { TribeAboutGroup } from '@dtypes/api.minmatar.org'
import { fill_template } from '@helpers/tribe_activity'
import { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']
type Translate = (key: UiKey) => string
type Totals = Record<string, number | string>

/** How one group's year reads on its tribe's About page. */
export type TribeAboutStage = {
    /** One word for what the group does: Mined, Hauled, Welcomed... */
    verb: UiKey
    value: (totals: Totals) => string
    unit: UiKey
    detail?: (t: Translate, totals: Totals) => string
    /** What the group's top pilots are ranked by, and how to print it. */
    pilot_metric: UiKey
    pilot_value: (value: number) => string
}

function n(totals: Totals, key: string): number {
    const raw = totals[key]
    const parsed = typeof raw === 'number' ? raw : Number(raw)
    return Number.isFinite(parsed) ? parsed : 0
}

function count(value: number): string {
    return number_thousand_separator(Math.round(value))
}

function short(value: number): string {
    return value >= 10_000 ? format_number(value) : count(value)
}

const KILLS: Pick<TribeAboutStage, 'pilot_metric' | 'pilot_value'> = {
    pilot_metric: 'tribes.about.metric.kills',
    pilot_value: count,
}

const FLEETS: Pick<TribeAboutStage, 'pilot_metric' | 'pilot_value'> = {
    pilot_metric: 'tribes.about.metric.fleets',
    pilot_value: count,
}

export const TRIBE_ABOUT_STAGES: Record<string, TribeAboutStage> = {
    'capitals.dreads': {
        verb: 'tribes.about.verb.siege',
        value: () => '',
        unit: 'tribes.about.unit.hulls',
        ...KILLS,
    },
    'capitals.carriers': {
        verb: 'tribes.about.verb.move',
        value: () => '',
        unit: 'tribes.about.unit.hulls',
        ...FLEETS,
    },
    'capitals.faxes': {
        verb: 'tribes.about.verb.save',
        value: () => '',
        unit: 'tribes.about.unit.hulls',
        ...FLEETS,
    },
    'supply.mining': {
        verb: 'tribes.about.verb.mined',
        value: (totals) => format_number(n(totals, 'total_volume_m3')),
        unit: 'tribes.about.unit.m3',
        detail: (t, totals) => fill_template(t('tribes.about.detail.ore_value'), {
            isk: format_isk(n(totals, 'total_isk_ore_market_estimate')),
        }),
        pilot_metric: 'tribes.about.metric.m3',
        pilot_value: format_number,
    },
    'supply.planetary-interaction': {
        verb: 'tribes.about.verb.extracted',
        value: (totals) => format_isk(n(totals, 'total_isk_pi_estimate')),
        unit: 'tribes.about.unit.isk',
        detail: (t) => t('tribes.about.detail.pi'),
        pilot_metric: 'tribes.about.metric.isk',
        pilot_value: format_isk,
    },
    'supply.subcapital-production': {
        verb: 'tribes.about.verb.built',
        value: (totals) => short(n(totals, 'delivered_units')),
        unit: 'tribes.about.unit.units',
        detail: (t, totals) => fill_template(t('tribes.about.detail.delivered'), {
            isk: format_isk(n(totals, 'delivered_estimate')),
        }),
        pilot_metric: 'tribes.about.metric.units',
        pilot_value: count,
    },
    'supply.capital-production': {
        verb: 'tribes.about.verb.built',
        value: (totals) => short(n(totals, 'delivered_units')),
        unit: 'tribes.about.unit.units',
        detail: (t, totals) => fill_template(t('tribes.about.detail.delivered'), {
            isk: format_isk(n(totals, 'delivered_estimate')),
        }),
        pilot_metric: 'tribes.about.metric.units',
        pilot_value: count,
    },
    'supply.freighters': {
        verb: 'tribes.about.verb.hauled',
        value: (totals) => short(n(totals, 'contracts_completed')),
        unit: 'tribes.about.unit.contracts',
        detail: (t, totals) => fill_template(t('tribes.about.detail.freight'), {
            m3: format_number(n(totals, 'total_volume_m3')),
            hours: count(n(totals, 'median_completion_hours')),
        }),
        pilot_metric: 'tribes.about.metric.contracts',
        pilot_value: count,
    },
    'supply.market': {
        verb: 'tribes.about.verb.sold',
        value: (totals) => short(n(totals, 'fits_sold')),
        unit: 'tribes.about.unit.fits',
        detail: (t, totals) => fill_template(t('tribes.about.detail.market'), {
            isk: format_isk(n(totals, 'isk_sold')),
            sellers: count(n(totals, 'sellers')),
        }),
        pilot_metric: 'tribes.about.metric.fits',
        pilot_value: count,
    },
    'supply.loyalty-points': {
        verb: 'tribes.about.verb.converted',
        value: (totals) => format_number(n(totals, 'lp_completed')),
        unit: 'tribes.about.unit.lp',
        detail: (t, totals) => fill_template(t('tribes.about.detail.lp'), {
            isk: format_isk(n(totals, 'isk_completed')),
            pilots: count(n(totals, 'pilots_paid')),
        }),
        pilot_metric: 'tribes.about.metric.lp',
        pilot_value: format_number,
    },
    'pulse.advocates': {
        verb: 'tribes.about.verb.welcomed',
        value: (totals) => short(n(totals, 'pilots_welcomed')),
        unit: 'tribes.about.unit.pilots',
        detail: (t, totals) => fill_template(t('tribes.about.detail.advocates'), {
            members: count(n(totals, 'full_members')),
            fleets: count(n(totals, 'first_fleets')),
        }),
        pilot_metric: 'tribes.about.metric.applications',
        pilot_value: count,
    },
    'pulse.fleet-commanders': {
        verb: 'tribes.about.verb.led',
        value: (totals) => short(n(totals, 'total_fleets')),
        unit: 'tribes.about.unit.fleets',
        detail: (t) => t('tribes.about.detail.fcs'),
        ...FLEETS,
    },
    'pulse.readiness': {
        verb: 'tribes.about.verb.readied',
        value: (totals) => short(n(totals, 'doctrine_updates')),
        unit: 'tribes.about.unit.doctrine_updates',
        detail: (t, totals) => fill_template(t('tribes.about.detail.readiness'), {
            pct: count(n(totals, 'flew_in_doctrine_pct')),
            fleets: count(n(totals, 'doctrine_fleets')),
        }),
        pilot_metric: 'tribes.about.metric.changes',
        pilot_value: count,
    },
    'pulse.technology': {
        verb: 'tribes.about.verb.fixed',
        value: (totals) => short(n(totals, 'tickets_resolved')),
        unit: 'tribes.about.unit.tickets',
        detail: (t, totals) => fill_template(t('tribes.about.detail.technology'), {
            pilots: count(n(totals, 'pilots_helped')),
            hours: count(n(totals, 'median_fix_hours')),
        }),
        pilot_metric: 'tribes.about.metric.tickets',
        pilot_value: count,
    },
    'pulse.thinkspeak': {
        verb: 'tribes.about.verb.told',
        value: (totals) => short(n(totals, 'posts_published') + n(totals, 'videos')),
        unit: 'tribes.about.unit.stories',
        detail: (t, totals) => fill_template(t('tribes.about.detail.thinkspeak'), {
            posts: count(n(totals, 'posts_published')),
            videos: count(n(totals, 'videos')),
        }),
        pilot_metric: 'tribes.about.metric.pieces',
        pilot_value: count,
    },
    'pulse.fishermen': {
        verb: 'tribes.about.verb.hunted',
        value: (totals) => short(n(totals, 'kills')),
        unit: 'tribes.about.unit.kills',
        detail: (t, totals) => fill_template(t('tribes.about.detail.fishermen'), {
            capitals: count(n(totals, 'capitals_caught_12mo')),
            supers: count(n(totals, 'supers_titans_all_time')),
        }),
        ...KILLS,
    },
    'pulse.tournaments': {
        verb: 'tribes.about.verb.competed',
        value: () => '',
        unit: 'tribes.about.unit.matches',
        pilot_metric: 'tribes.about.metric.matches',
        pilot_value: count,
    },
}

/** Siege, move, save. */
export const CAPITALS_ORDER = [
    'capitals.dreads',
    'capitals.carriers',
    'capitals.faxes',
]

/** Ore to hangar to market: the order Supply's groups hand work along. */
export const SUPPLY_FLOW = [
    'supply.mining',
    'supply.planetary-interaction',
    'supply.subcapital-production',
    'supply.capital-production',
    'supply.freighters',
    'supply.market',
    'supply.loyalty-points',
]

/** Pulse reads as a pilot's path: welcomed, led, readied, then the rest. */
export const PULSE_ORDER = [
    'pulse.advocates',
    'pulse.fleet-commanders',
    'pulse.readiness',
    'pulse.technology',
    'pulse.thinkspeak',
    'pulse.fishermen',
    'pulse.tournaments',
]

/** Groups in ``order`` first, then any the list doesn't know, by name. */
export function order_groups(
    groups: TribeAboutGroup[],
    order: string[],
): TribeAboutGroup[] {
    const rank = (code: string) => {
        const index = order.indexOf(code)
        return index === -1 ? order.length : index
    }
    return [...groups].sort((a, b) =>
        rank(a.code) - rank(b.code) || a.name.localeCompare(b.name),
    )
}

/** A group's year has something to show (not manual, not all zeros). */
export function group_has_year(group: TribeAboutGroup): boolean {
    if (group.manual)
        return false
    return Object.values(group.totals ?? {}).some((value) => Number(value) > 0)
}

/** Month keys from the first one with any value, so a young tribe has no empty run-up. */
export function trim_leading_zeros<T>(rows: T[], value: (row: T) => number): T[] {
    const first = rows.findIndex((row) => value(row) > 0)
    return first === -1 ? [] : rows.slice(first)
}

export function month_short(month: string, lang: string): string {
    const [year, mm] = month.split('-').map(Number)
    return new Date(Date.UTC(year, mm - 1, 1)).toLocaleDateString(lang, {
        month: 'short',
        timeZone: 'UTC',
    })
}
