import type { BuybackLedgerEntry } from '@dtypes/api.minmatar.org'

export type BuybackStockpileSaleBuyer = {
    counterparty_id: number | null
    counterparty_name: string
    counterparty_kind: 'character' | 'corporation' | null
}

export type BuybackStockpileSaleRow = {
    day: string
    type_id: number
    name: string
    reason: string
    quantity: number
    isk_total: number | null
    occurred_at: string
    sale_count: number
    buyers: BuybackStockpileSaleBuyer[]
}

const SALE_REASONS = new Set(['sold_order', 'sold_contract'])

function day_key(iso: string): string {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return iso.slice(0, 10)
    return date.toISOString().slice(0, 10)
}

function sale_isk(entry: BuybackLedgerEntry): number | null {
    const value = entry.isk_value ?? entry.isk_total
    return value == null ? null : value
}

function buyer_from_entry(entry: BuybackLedgerEntry): BuybackStockpileSaleBuyer | null {
    if (!entry.counterparty_id && !entry.counterparty_name) return null
    return {
        counterparty_id: entry.counterparty_id ?? null,
        counterparty_name: entry.counterparty_name || String(entry.counterparty_id),
        counterparty_kind: entry.counterparty_kind ?? null,
    }
}

function buyer_key(buyer: BuybackStockpileSaleBuyer): string {
    if (buyer.counterparty_id != null) return `${buyer.counterparty_kind || 'id'}:${buyer.counterparty_id}`
    return `name:${buyer.counterparty_name}`
}

export function aggregate_stockpile_sales(
    entries: BuybackLedgerEntry[],
): BuybackStockpileSaleRow[] {
    const groups = new Map<string, BuybackStockpileSaleRow>()

    for (const entry of entries) {
        if (!SALE_REASONS.has(entry.reason)) continue

        const day = day_key(entry.occurred_at)
        const key = `${day}|${entry.type_id}|${entry.reason}`
        const isk = sale_isk(entry)
        const existing = groups.get(key)

        if (!existing) {
            const buyer = buyer_from_entry(entry)
            groups.set(key, {
                day,
                type_id: entry.type_id,
                name: entry.name,
                reason: entry.reason,
                quantity: entry.quantity,
                isk_total: isk,
                occurred_at: entry.occurred_at,
                sale_count: 1,
                buyers: buyer ? [buyer] : [],
            })
            continue
        }

        existing.quantity += entry.quantity
        existing.sale_count += 1
        if (isk != null) {
            existing.isk_total = (existing.isk_total ?? 0) + isk
        }
        if (new Date(entry.occurred_at).getTime() > new Date(existing.occurred_at).getTime()) {
            existing.occurred_at = entry.occurred_at
        }

        const buyer = buyer_from_entry(entry)
        if (buyer) {
            const seen = new Set(existing.buyers.map(buyer_key))
            const next = buyer_key(buyer)
            if (!seen.has(next)) existing.buyers.push(buyer)
        }
    }

    return [...groups.values()].sort((a, b) => {
        const by_day = b.day.localeCompare(a.day)
        if (by_day !== 0) return by_day
        const by_time = new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime()
        if (by_time !== 0) return by_time
        return a.name.localeCompare(b.name)
    })
}
