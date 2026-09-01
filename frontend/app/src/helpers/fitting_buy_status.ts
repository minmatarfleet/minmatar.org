import type { TagColors } from '@dtypes/layout_components'

export const FITTING_BUY_STATUSES = [
    'draft',
    'pending_fitting',
    'completed',
    'archived',
] as const

export type FittingBuyStatus = (typeof FITTING_BUY_STATUSES)[number]

function is_fitting_buy_status(status: string): status is FittingBuyStatus {
    return (FITTING_BUY_STATUSES as readonly string[]).includes(status)
}

export function normalize_fitting_buy_status(status: string): FittingBuyStatus {
    if (status === 'purchased')
        return 'completed'
    if (is_fitting_buy_status(status))
        return status
    return 'draft'
}

export function is_fitting_buy_complete(status: string): boolean {
    const normalized = normalize_fitting_buy_status(status)
    return normalized === 'completed' || normalized === 'archived'
}

export function fitting_buy_status_label(status: string, t: (k: string) => string): string {
    const normalized = normalize_fitting_buy_status(status)
    switch (normalized) {
        case 'pending_fitting':
            return t('fitting_buy.status.pending_fitting')
        case 'completed':
            return t('fitting_buy.status.completed')
        case 'archived':
            return t('fitting_buy.status.archived')
        case 'draft':
            return t('fitting_buy.status.draft')
        default: {
            const _exhaustive: never = normalized
            return _exhaustive
        }
    }
}

export function fitting_buy_status_color(status: string): TagColors {
    const normalized = normalize_fitting_buy_status(status)
    switch (normalized) {
        case 'pending_fitting':
            return 'fleet-yellow'
        case 'completed':
            return 'green'
        case 'archived':
            return 'militia-purple'
        case 'draft':
            return 'alliance-blue'
        default: {
            const _exhaustive: never = normalized
            return _exhaustive
        }
    }
}
