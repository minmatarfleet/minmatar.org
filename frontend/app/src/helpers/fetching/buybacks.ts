import type { BuybackContract } from '@dtypes/api.minmatar.org'
import { get_buyback_contracts } from '@helpers/api.minmatar.org/buybacks'

const STATUS_SORT_ORDER: Record<string, number> = {
    outstanding: 0,
    in_progress: 1,
    finished: 2,
}

export async function fetch_buyback_contracts(history: boolean = false): Promise<BuybackContract[]> {
    const contracts = await get_buyback_contracts(history)

    return contracts.sort((a, b) => {
        const status_diff = (STATUS_SORT_ORDER[a.status] ?? 99) - (STATUS_SORT_ORDER[b.status] ?? 99)
        if (status_diff !== 0)
            return status_diff

        const a_date = new Date(a.status === 'finished' ? (a.date_completed ?? a.date_issued) : a.date_issued).getTime()
        const b_date = new Date(b.status === 'finished' ? (b.date_completed ?? b.date_issued) : b.date_issued).getTime()
        return b_date - a_date
    })
}
