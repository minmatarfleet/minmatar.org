import { describe, expect, it } from 'vitest'
import {
    fitting_buy_status_color,
    fitting_buy_status_label,
    is_fitting_buy_complete,
    normalize_fitting_buy_status,
} from '@helpers/fitting_buy_status'

const t = (key: string) => key

describe('fitting buy status', () => {
    it('renames purchased to completed', () => {
        expect(normalize_fitting_buy_status('purchased')).toBe('completed')
        expect(is_fitting_buy_complete('purchased')).toBe(true)
        expect(is_fitting_buy_complete('completed')).toBe(true)
        expect(is_fitting_buy_complete('draft')).toBe(false)
        expect(fitting_buy_status_label('purchased', t)).toBe(
            'fitting_buy.status.completed',
        )
        expect(fitting_buy_status_color('completed')).toBe('green')
    })
})
