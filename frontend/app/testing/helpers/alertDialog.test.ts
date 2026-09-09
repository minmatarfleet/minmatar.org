import { describe, expect, it, vi } from 'vitest'
import { schedule_alert_dialog_reset } from '@helpers/alertDialog'

describe('schedule_alert_dialog_reset', () => {
    it('defers finish when Accept has an external href so the Open link can navigate', () => {
        const finish = vi.fn()
        const defer = vi.fn()

        schedule_alert_dialog_reset({
            action: 'accept',
            accept_href: 'https://developers.eveonline.com/authorized-apps',
            finish,
            defer,
        })

        expect(finish).not.toHaveBeenCalled()
        expect(defer).toHaveBeenCalledTimes(1)
        defer.mock.calls[0][0]()
        expect(finish).toHaveBeenCalledTimes(1)
    })

    it('finishes immediately on Cancel', () => {
        const finish = vi.fn()
        const defer = vi.fn()

        schedule_alert_dialog_reset({
            action: 'close',
            accept_href: 'https://developers.eveonline.com/authorized-apps',
            finish,
            defer,
        })

        expect(defer).not.toHaveBeenCalled()
        expect(finish).toHaveBeenCalledTimes(1)
    })

    it('finishes immediately when Accept has no href', () => {
        const finish = vi.fn()
        const defer = vi.fn()

        schedule_alert_dialog_reset({
            action: 'accept',
            accept_href: '',
            finish,
            defer,
        })

        expect(defer).not.toHaveBeenCalled()
        expect(finish).toHaveBeenCalledTimes(1)
    })
})
