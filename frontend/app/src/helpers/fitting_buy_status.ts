import type { TagColors } from '@dtypes/layout_components'

export const FITTING_BUY_STATUSES = [
    'draft',
    'pending_fitting',
    'purchased',
    'archived',
] as const

export type FittingBuyStatus = (typeof FITTING_BUY_STATUSES)[number]

export function fitting_buy_status_label(status: string, t: (k: string) => string): string {
    switch (status) {
        case 'pending_fitting':
            return t('fitting_buy.status.pending_fitting')
        case 'purchased':
            return t('fitting_buy.status.purchased')
        case 'archived':
            return t('fitting_buy.status.archived')
        case 'draft':
        default:
            return t('fitting_buy.status.draft')
    }
}

export function fitting_buy_status_color(status: string): TagColors {
    switch (status) {
        case 'pending_fitting':
            return 'fleet-yellow'
        case 'purchased':
            return 'green'
        case 'archived':
            return 'militia-purple'
        case 'draft':
        default:
            return 'alliance-blue'
    }
}
