import type { TranslationKey } from '@helpers/i18n'

type Translate = (key: TranslationKey) => string

function counted(t: Translate, count: number, one: TranslationKey, many: TranslationKey) {
    return count === 1 ? t(one) : t(many).replace('~COUNT', String(count))
}

/** "1 doctrine fit · 2 fitting items · 3 items": the Keep in stock summary. */
export function hub_stock_summary(t: Translate, contracts: number, fittings: number, items: number): string {
    return [
        counted(t, contracts, 'admin_hubs.count_contracts_one', 'admin_hubs.count_contracts'),
        counted(t, fittings, 'admin_hubs.count_fittings_one', 'admin_hubs.count_fittings'),
        counted(t, items, 'admin_hubs.count_items_one', 'admin_hubs.count_items'),
    ].join(' · ')
}
