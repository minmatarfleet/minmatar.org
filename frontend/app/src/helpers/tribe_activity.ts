import {
    format_hours,
    format_isk,
    format_number,
    format_volume_m3,
    number_thousand_separator,
} from '@helpers/numbers'
import type { TribeShowcaseHighlights } from '@dtypes/api.minmatar.org'
import { ui } from '@i18n/ui'

type Translate = (key: keyof typeof ui['en']) => string
type Totals = Record<string, number | string>
type Values = Record<string, number>

export type TribeActivityMetric = {
    label: string
    value: string
    hint?: string
    coming_soon?: boolean
}

/** Group-specific showcase block rendered under the metric cards. */
export type TribeActivityBlock =
    | 'hulls'
    | 'weekly'
    | 'welcomed'
    | 'doctrine_grid'
    | 'fixed'
    | 'latest_work'
    | 'trophy_case'
    | 'catches'

export type TribeActivityAllTime = {
    headline: string
    detail: string
    /** 0–1 toward the next milestone, when there is one. */
    progress?: number
}

export type TribeActivityContributors = {
    metric_label: string
    value: (values: Values) => string
    detail?: (values: Values) => string
}

export type TribeActivitySpec = {
    metrics: (
        t: Translate,
        totals: Totals,
        highlights: TribeShowcaseHighlights,
    ) => TribeActivityMetric[]
    block?: TribeActivityBlock
    all_time?: (
        t: Translate,
        highlights: TribeShowcaseHighlights,
    ) => TribeActivityAllTime | null
    contributors?: (t: Translate) => TribeActivityContributors
    /** Nothing stored to measure yet: render the coming-soon layout. */
    coming_soon?: boolean
}

function total_number(totals: Totals, key: string): number {
    const raw = totals[key]
    const parsed = typeof raw === 'number' ? raw : Number(raw)
    return Number.isFinite(parsed) ? parsed : 0
}

function count(value: number | null | undefined): string {
    return number_thousand_separator(Math.round(value ?? 0))
}

/** Replace `{name}` placeholders in a translated string. */
export function fill_template(template: string, values: Record<string, string>): string {
    return Object.entries(values).reduce(
        (text, [key, value]) => text.replaceAll(`{${key}}`, value),
        template,
    )
}

/** Pick the `_one` key when n is 1; both keys take `{n}`. */
export function plural(
    t: Translate,
    n: number | undefined,
    key: keyof typeof ui['en'],
): string {
    const one_key = `${key}_one` as keyof typeof ui['en']
    const template = n === 1 && ui.en[one_key] ? t(one_key) : t(key)
    return fill_template(template, { n: count(n) })
}

/** Join the non-zero parts, e.g. "2 supers · 19 capitals". */
function nonzero_parts(
    t: Translate,
    parts: [number | undefined, keyof typeof ui['en']][],
): string {
    return parts
        .filter(([n]) => (n ?? 0) > 0)
        .map(([n, key]) => plural(t, n, key))
        .join(' · ')
}

function best_month(
    t: Translate,
    highlights: TribeShowcaseHighlights,
    format: (value: number) => string = count,
): string | undefined {
    const best = highlights.best_month
    return best
        ? fill_template(t('tribes.activity.best_month'), { value: format(best.value) })
        : undefined
}

function soon(label: string, hint: string): TribeActivityMetric {
    return { label, value: '', hint, coming_soon: true }
}

function all_time_number(
    highlights: TribeShowcaseHighlights,
    key: string,
): number {
    return Number(highlights.all_time?.[key] ?? 0)
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
    'supply.market': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.market.fits_sold'),
                value: count(total_number(totals, 'fits_sold')),
                hint: best_month(t, highlights),
            },
            {
                label: t('tribes.activity.market.isk_sold'),
                value: format_isk(total_number(totals, 'isk_sold')),
                hint: t('tribes.activity.market.isk_sold_hint'),
            },
            {
                label: t('tribes.activity.market.fits_listed'),
                value: count(total_number(totals, 'fits_listed')),
                hint: t('tribes.activity.market.fits_listed_hint'),
            },
            {
                label: t('tribes.activity.market.sellers'),
                value: count(total_number(totals, 'sellers')),
                hint: t('tribes.activity.market.sellers_hint'),
            },
        ],
        block: 'hulls',
        all_time: (t, highlights) => {
            if (!highlights.all_time)
                return null
            const sold = all_time_number(highlights, 'fits_sold')
            const target = all_time_number(highlights, 'next_milestone')
            return {
                headline: fill_template(t('tribes.activity.market.all_time'), { n: count(sold) }),
                detail: target
                    ? fill_template(t('tribes.activity.next_milestone'), {
                        left: count(target - sold),
                        target: count(target),
                    })
                    : '',
                progress: target ? sold / target : undefined,
            }
        },
        contributors: (t) => ({
            metric_label: t('tribes.activity.market.fits_sold'),
            value: (values) => count(values.fits_sold),
            detail: (values) => fill_template(t('tribes.activity.market.contributor_detail'), {
                isk: format_isk(values.isk_sold ?? 0),
            }),
        }),
    },
    'supply.loyalty-points': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.lp.lp_completed'),
                value: format_number(total_number(totals, 'lp_completed')),
                hint: best_month(t, highlights, (value) => format_number(value)),
            },
            {
                label: t('tribes.activity.lp.isk_completed'),
                value: format_isk(total_number(totals, 'isk_completed')),
                hint: fill_template(t('tribes.activity.lp.isk_completed_hint'), {
                    n: count(total_number(totals, 'completed')),
                }),
            },
            {
                label: t('tribes.activity.lp.pilots_paid'),
                value: count(total_number(totals, 'pilots_paid')),
                hint: t('tribes.activity.lp.pilots_paid_hint'),
            },
            {
                label: t('tribes.activity.lp.within_day'),
                value: `${total_number(totals, 'paid_within_day_pct')}%`,
                hint: t('tribes.activity.lp.within_day_hint'),
            },
        ],
        block: 'weekly',
        all_time: (t, highlights) => highlights.all_time
            ? {
                headline: fill_template(t('tribes.activity.lp.all_time'), {
                    isk: format_isk(all_time_number(highlights, 'isk')),
                }),
                detail: fill_template(t('tribes.activity.lp.all_time_detail'), {
                    lp: format_number(all_time_number(highlights, 'lp')),
                    pilots: count(all_time_number(highlights, 'pilots')),
                }),
            }
            : null,
        contributors: (t) => ({
            metric_label: t('tribes.activity.lp.lp_completed'),
            value: (values) => `${format_number(values.lp ?? 0)} LP`,
            detail: (values) => plural(t, values.orders, 'tribes.activity.lp.contributor_detail'),
        }),
    },
    'pulse.advocates': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.advocates.pilots_welcomed'),
                value: count(total_number(totals, 'pilots_welcomed')),
                hint: best_month(t, highlights),
            },
            {
                label: t('tribes.activity.advocates.full_members'),
                value: count(total_number(totals, 'full_members')),
                hint: t('tribes.activity.advocates.full_members_hint'),
            },
            {
                label: t('tribes.activity.advocates.academy_pilots'),
                value: count(total_number(totals, 'academy_pilots')),
                hint: t('tribes.activity.advocates.academy_pilots_hint'),
            },
            {
                label: t('tribes.activity.advocates.first_fleets'),
                value: count(total_number(totals, 'first_fleets')),
                hint: t('tribes.activity.advocates.first_fleets_hint'),
            },
        ],
        block: 'welcomed',
        all_time: (t, highlights) => highlights.all_time
            ? {
                headline: fill_template(t('tribes.activity.advocates.all_time'), {
                    n: count(all_time_number(highlights, 'pilots_welcomed')),
                }),
                detail: fill_template(t('tribes.activity.advocates.all_time_detail'), {
                    n: count(all_time_number(highlights, 'still_flying')),
                }),
            }
            : null,
        contributors: (t) => ({
            metric_label: t('tribes.activity.advocates.contributor_metric'),
            value: (values) => count(values.applications_accepted),
        }),
    },
    'pulse.readiness': {
        metrics: (t, totals) => [
            {
                label: t('tribes.activity.readiness.doctrine_updates'),
                value: count(total_number(totals, 'doctrine_updates')),
                hint: t('tribes.activity.readiness.doctrine_updates_hint'),
            },
            {
                label: t('tribes.activity.readiness.flew_in_doctrine'),
                value: `${total_number(totals, 'flew_in_doctrine_pct')}%`,
                hint: fill_template(t('tribes.activity.readiness.flew_in_doctrine_hint'), {
                    n: count(total_number(totals, 'doctrine_fleets')),
                }),
            },
            soon(
                t('tribes.activity.readiness.ready_pilots'),
                t('tribes.activity.readiness.ready_pilots_hint'),
            ),
            soon(
                t('tribes.activity.readiness.newly_ready'),
                t('tribes.activity.readiness.newly_ready_hint'),
            ),
        ],
        block: 'doctrine_grid',
        contributors: (t) => ({
            metric_label: t('tribes.activity.readiness.contributor_metric'),
            value: (values) => count(values.doctrine_changes),
            detail: (values) => fill_template(t('tribes.activity.readiness.contributor_detail'), {
                proposed: count(values.changes_proposed),
                reviewed: count(values.changes_reviewed),
            }),
        }),
    },
    'pulse.technology': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.technology.tickets_resolved'),
                value: count(total_number(totals, 'tickets_resolved')),
                hint: best_month(t, highlights),
            },
            {
                label: t('tribes.activity.technology.median_fix'),
                value: `${format_hours(total_number(totals, 'median_fix_hours'))}h`,
                hint: t('tribes.activity.technology.median_fix_hint'),
            },
            {
                label: t('tribes.activity.technology.pilots_helped'),
                value: count(total_number(totals, 'pilots_helped')),
                hint: t('tribes.activity.technology.pilots_helped_hint'),
            },
            {
                label: t('tribes.activity.technology.desktop_pilots'),
                value: count(total_number(totals, 'desktop_app_pilots')),
                hint: t('tribes.activity.technology.desktop_pilots_hint'),
            },
        ],
        block: 'fixed',
        all_time: (t, highlights) => highlights.all_time
            ? {
                headline: fill_template(t('tribes.activity.technology.all_time'), {
                    n: count(all_time_number(highlights, 'pilots_helped')),
                }),
                detail: t('tribes.activity.technology.all_time_detail'),
            }
            : null,
        contributors: (t) => ({
            metric_label: t('tribes.activity.technology.tickets_resolved'),
            value: (values) => count(values.tickets_resolved),
            detail: (values) => fill_template(t('tribes.activity.technology.contributor_detail'), {
                hours: format_hours(values.median_fix_hours ?? 0),
            }),
        }),
    },
    'pulse.thinkspeak': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.thinkspeak.posts'),
                value: count(total_number(totals, 'posts_published')),
                hint: highlights.best_quarter
                    ? fill_template(t('tribes.activity.best_quarter'), {
                        value: count(highlights.best_quarter),
                    })
                    : undefined,
            },
            {
                label: t('tribes.activity.thinkspeak.videos'),
                value: count(total_number(totals, 'videos')),
                hint: t('tribes.activity.thinkspeak.videos_hint'),
            },
            {
                label: t('tribes.activity.thinkspeak.writers'),
                value: count(total_number(totals, 'writers')),
                hint: t('tribes.activity.thinkspeak.writers_hint'),
            },
            {
                label: t('tribes.activity.thinkspeak.creators'),
                value: count(total_number(totals, 'creators')),
                hint: t('tribes.activity.thinkspeak.creators_hint'),
            },
        ],
        block: 'latest_work',
        all_time: (t, highlights) => {
            if (!highlights.all_time)
                return null
            const posts = all_time_number(highlights, 'posts')
            const videos = all_time_number(highlights, 'videos')
            return {
                headline: fill_template(t('tribes.activity.thinkspeak.all_time'), {
                    n: count(posts + videos),
                }),
                detail: fill_template(t('tribes.activity.thinkspeak.all_time_detail'), {
                    posts: count(posts),
                    videos: count(videos),
                }),
            }
        },
        contributors: (t) => ({
            metric_label: t('tribes.activity.thinkspeak.contributor_metric'),
            value: (values) => count(values.pieces),
            detail: (values) => nonzero_parts(t, [
                [values.posts, 'tribes.activity.thinkspeak.contributor_posts'],
                [values.videos, 'tribes.activity.thinkspeak.contributor_videos'],
            ]),
        }),
    },
    'pulse.tournaments': {
        coming_soon: true,
        metrics: (t) => [
            soon(
                t('tribes.activity.tournaments.matches'),
                t('tribes.activity.tournaments.matches_hint'),
            ),
            soon(
                t('tribes.activity.tournaments.record'),
                t('tribes.activity.tournaments.record_hint'),
            ),
            soon(
                t('tribes.activity.tournaments.best_finish'),
                t('tribes.activity.tournaments.best_finish_hint'),
            ),
            soon(
                t('tribes.activity.tournaments.pilots'),
                t('tribes.activity.tournaments.pilots_hint'),
            ),
        ],
        block: 'trophy_case',
    },
    'pulse.fishermen': {
        metrics: (t, totals, highlights) => [
            {
                label: t('tribes.activity.fishermen.kills'),
                value: count(total_number(totals, 'kills')),
                hint: best_month(t, highlights),
            },
            {
                label: t('tribes.activity.fishermen.hunters'),
                value: count(total_number(totals, 'hunters')),
                hint: t('tribes.activity.fishermen.hunters_hint'),
            },
            {
                label: t('tribes.activity.fishermen.capitals'),
                value: count(total_number(totals, 'capitals_caught_12mo')),
                hint: t('tribes.activity.fishermen.capitals_hint'),
            },
            {
                label: t('tribes.activity.fishermen.supers'),
                value: count(total_number(totals, 'supers_titans_all_time')),
                hint: t('tribes.activity.fishermen.supers_hint'),
            },
        ],
        block: 'catches',
        all_time: (t, highlights) => all_time_number(highlights, 'capitals') > 0
            ? {
                headline: nonzero_parts(t, [
                    [all_time_number(highlights, 'titans'), 'tribes.activity.fishermen.all_time_titans'],
                    [all_time_number(highlights, 'supers'), 'tribes.activity.fishermen.all_time_supers'],
                    [all_time_number(highlights, 'capitals'), 'tribes.activity.fishermen.all_time_capitals'],
                ]),
                detail: t('tribes.activity.fishermen.all_time_detail'),
            }
            : null,
        contributors: (t) => ({
            metric_label: t('tribes.activity.fishermen.kills'),
            value: (values) => count(values.kill_count),
            detail: (values) => values.capitals_caught
                ? plural(t, values.capitals_caught, 'tribes.activity.fishermen.contributor_detail')
                : '',
        }),
    },
}

/** Period label key for a showcase period such as "30d" or "90d". */
/** "in under an hour", "in 5.2h" or "in 12d" for a ticket's fix time. */
export function fix_time(t: Translate, hours: number): string {
    if (hours < 1)
        return t('tribes.activity.technology.fixed_under_hour')
    const time = hours < 48 ? `${format_hours(hours)}h` : `${Math.round(hours / 24)}d`
    return fill_template(t('tribes.activity.technology.fixed_in'), { time })
}

export function showcase_period_key(
    period: string | undefined,
): 'tribes.showcase.last_30d' | 'tribes.showcase.last_90d' {
    return period === '90d' ? 'tribes.showcase.last_90d' : 'tribes.showcase.last_30d'
}
