import { describe, expect, it } from 'vitest'

import { hub_stock_summary } from '@helpers/market_hub_settings'
import { i18n } from '@helpers/i18n'

const { t } = i18n(new URL('http://localhost/market/ops/hubs/'))

describe('hub_stock_summary', () => {
    it('counts each kind, singular at one', () => {
        expect(hub_stock_summary(t, 1, 1, 2)).toBe('1 doctrine fit · 1 fitting item · 2 items')
        expect(hub_stock_summary(t, 0, 3, 1)).toBe('0 doctrine fits · 3 fitting items · 1 item')
    })
})
